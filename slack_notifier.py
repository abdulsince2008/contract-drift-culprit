import os
from typing import List, Dict, Any, Optional
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackNotifier:
    def __init__(self, token: str = None, channel: str = None):
        self.token = token or os.getenv("SLACK_BOT_TOKEN")
        self.channel = channel or os.getenv("SLACK_CHANNEL")
        self.client = WebClient(token=self.token) if self.token else None

    def send_drift_report(self, report: Dict[str, Any], repo_url: str = None) -> bool:
        if not self.client or not self.channel:
            return False
        
        try:
            blocks = self._build_report_blocks(report, repo_url)
            self.client.chat_postMessage(
                channel=self.channel,
                blocks=blocks,
                text="API Contract Drift Report"
            )
            return True
        except SlackApiError as e:
            print(f"Slack API error: {e.response['error']}")
            return False

    def _build_report_blocks(self, report: Dict[str, Any], repo_url: str = None) -> List[Dict]:
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🔍 API Contract Drift Detected",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Total Breaking Changes:* {report['total_breaking_changes']}"
                }
            }
        ]
        
        if repo_url:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Repository: <{repo_url}|{repo_url}>"
                    }
                ]
            })
        
        blocks.append({"type": "divider"})
        
        for idx, result in enumerate(report["results"], 1):
            change = result["breaking_change"]
            culprits = result["culprit_commits"]
            
            change_text = (
                f"*{idx}. {change['method']} {change['path']}*\n"
                f"Type: `{change['change_type']}`\n"
                f"Description: {change['description']}"
            )
            
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": change_text}
            })
            
            if culprits:
                culprit_text = "*Top Suspect Commits:*\n"
                for c in culprits[:3]:
                    culprit_text += (
                        f"• `{c['commit_hash']}` by {c['author']} ({c['date']})\n"
                        f"  _{c['message']}_\n"
                        f"  Files: {', '.join(c['files_changed'][:3])}\n"
                    )
                if len(culprits) > 3:
                    culprit_text += f"  ... and {len(culprits) - 3} more commits\n"
            else:
                culprit_text = "*No matching commits found in route handlers_"
            
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": culprit_text}
            })
            
            if idx < len(report["results"]):
                blocks.append({"type": "divider"})
        
        return blocks

    def send_simple_message(self, text: str) -> bool:
        if not self.client or not self.channel:
            return False
        
        try:
            self.client.chat_postMessage(channel=self.channel, text=text)
            return True
        except SlackApiError as e:
            print(f"Slack API error: {e.response['error']}")
            return False