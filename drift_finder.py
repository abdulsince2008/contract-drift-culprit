import subprocess
import json
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class BreakingChange:
    path: str
    method: str
    change_type: str
    description: str
    old_spec: Dict[str, Any]
    new_spec: Dict[str, Any]


@dataclass
class CulpritCommit:
    commit_hash: str
    author: str
    author_email: str
    date: str
    message: str
    files_changed: List[str]
    matched_path: str


class OASDiffRunner:
    def __init__(self, oasdiff_path: str = "oasdiff"):
        self.oasdiff_path = oasdiff_path

    def diff(self, old_spec: str, new_spec: str) -> List[BreakingChange]:
        """Run oasdiff and parse breaking changes."""
        cmd = [
            self.oasdiff_path,
            "breaking",
            old_spec,
            new_spec,
            "-f", "json"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired:
            raise RuntimeError("oasdiff timed out after 60 seconds")
        except FileNotFoundError:
            raise RuntimeError(f"oasdiff not found at {self.oasdiff_path}. Install it with: go install github.com/oasdiff/oasdiff@latest")

        if result.returncode != 0 and result.returncode != 1:
            raise RuntimeError(f"oasdiff failed: {result.stderr}")

        try:
            data = json.loads(result.stdout) if result.stdout.strip() else {}
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse oasdiff output: {e}")

        return self._parse_breaking_changes(data)

    def _parse_breaking_changes(self, data: List[Dict[str, Any]]) -> List[BreakingChange]:
        changes = []
        
        for breaking in data:
            path = breaking.get("path", "")
            method = breaking.get("operation", "").upper()
            change_type = breaking.get("id", "")
            description = breaking.get("text", "")
            
            old_spec = breaking.get("baseSource", {})
            new_spec = breaking.get("revisionSource", {})
            
            changes.append(BreakingChange(
                path=path,
                method=method,
                change_type=change_type,
                description=description,
                old_spec=old_spec,
                new_spec=new_spec
            ))
        
        return changes


class GitBlameAnalyzer:
    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path).resolve()
        
    def find_culprit_for_path(self, api_path: str, method: str, 
                              route_patterns: List[str] = None) -> List[CulpritCommit]:
        """
        Find commits that likely introduced changes to the given API path.
        Uses git log with path filtering based on common route handler patterns.
        """
        route_patterns = route_patterns or self._default_route_patterns()
        
        candidate_files = self._find_candidate_files(api_path, method, route_patterns)
        
        if not candidate_files:
            return []
        
        all_commits = []
        for file_path in candidate_files:
            commits = self._get_git_log_for_file(file_path)
            all_commits.extend(commits)
        
        unique_commits = self._deduplicate_commits(all_commits)
        unique_commits.sort(key=lambda c: c.date, reverse=True)
        
        return unique_commits[:10]

    def _default_route_patterns(self) -> List[str]:
        return [
            "**/routes/**/*.py",
            "**/controllers/**/*.py",
            "**/handlers/**/*.py",
            "**/api/**/*.py",
            "**/views/**/*.py",
            "**/endpoints/**/*.py",
            "**/routers/**/*.py",
            "**/*.py"
        ]

    def _find_candidate_files(self, api_path: str, method: str, 
                              patterns: List[str]) -> List[str]:
        candidate_files = []
        path_parts = [p for p in api_path.strip("/").split("/") if p]
        
        for pattern in patterns:
            for file_path in self.repo_path.glob(pattern):
                if file_path.is_file():
                    try:
                        content = file_path.read_text()
                        if self._file_matches_route(content, api_path, method, path_parts):
                            candidate_files.append(str(file_path.relative_to(self.repo_path)))
                    except (UnicodeDecodeError, PermissionError):
                        continue
        
        return list(set(candidate_files))

    def _file_matches_route(self, content: str, api_path: str, method: str, 
                            path_parts: List[str]) -> bool:
        content_lower = content.lower()
        method_lower = method.lower()
        
        if method_lower in content_lower:
            for part in path_parts:
                if part.lower() in content_lower:
                    return True
        
        path_normalized = api_path.replace("{", "").replace("}", "").replace("/", ".")
        if path_normalized in content_lower:
            return True
            
        return False

    def _get_git_log_for_file(self, file_path: str) -> List[CulpritCommit]:
        cmd = [
            "git", "-C", str(self.repo_path),
            "log", "--oneline", "--pretty=format:%H|%an|%ae|%ad|%s",
            "--date=short", "--", file_path
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            return []
        
        if result.returncode != 0:
            return []
        
        commits = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|", 4)
            if len(parts) == 5:
                commit_hash, author, email, date, message = parts
                commits.append(CulpritCommit(
                    commit_hash=commit_hash[:8],
                    author=author,
                    author_email=email,
                    date=date,
                    message=message,
                    files_changed=[file_path],
                    matched_path=file_path
                ))
        
        return commits

    def _deduplicate_commits(self, commits: List[CulpritCommit]) -> List[CulpritCommit]:
        seen = {}
        for commit in commits:
            if commit.commit_hash not in seen:
                seen[commit.commit_hash] = commit
            else:
                seen[commit.commit_hash].files_changed.extend(commit.files_changed)
                seen[commit.commit_hash].files_changed = list(set(seen[commit.commit_hash].files_changed))
        return list(seen.values())


class DriftCulpritFinder:
    def __init__(self, repo_path: str = ".", oasdiff_path: str = "oasdiff"):
        self.oasdiff = OASDiffRunner(oasdiff_path)
        self.git_analyzer = GitBlameAnalyzer(repo_path)

    def analyze(self, old_spec: str, new_spec: str, 
                route_patterns: List[str] = None) -> Dict[str, Any]:
        breaking_changes = self.oasdiff.diff(old_spec, new_spec)
        
        results = []
        for change in breaking_changes:
            culprits = self.git_analyzer.find_culprit_for_path(
                change.path, change.method, route_patterns
            )
            
            results.append({
                "breaking_change": asdict(change),
                "culprit_commits": [asdict(c) for c in culprits]
            })
        
        return {
            "total_breaking_changes": len(breaking_changes),
            "results": results
        }