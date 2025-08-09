"""
Discord ROAS Bot Emoji Audit Tool
Comprehensive emoji usage analysis for panel components
"""

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EmojiUsage:
    """Record of emoji usage in source code"""
    emoji: str
    file_path: str
    line_number: int
    line_content: str
    context_type: str  # 'embed_title', 'embed_field', 'button_label', 'button_emoji', etc.


@dataclass
class EmojiAnalysis:
    """Analysis result for a specific emoji"""
    emoji: str
    usage_count: int
    files_used: list[str]
    contexts: list[str]
    is_functional: bool
    purpose_description: str
    recommendation: str  # 'KEEP', 'REMOVE', 'REVIEW'
    reasoning: str


class EmojiAuditTool:
    """Tool for comprehensive emoji audit of Discord panel components"""

    def __init__(self, root_path: str):
        self.root_path = Path(root_path)
        self.emoji_usages: list[EmojiUsage] = []
        self.functional_patterns = self._define_functional_patterns()

    def _define_functional_patterns(self) -> dict[str, set[str]]:
        """Define patterns that indicate functional emoji usage"""
        return {
            'status_indicators': {
                '✅', '❌', '⚠', '🔴', '🟢', '🟡', '⚪', '🔵'
            },
            'navigation': {
                '➡', '⬅', '🔙', '🔄', '↗', '↙', '⬆', '⬇'
            },
            'currency_system': {
                '💰', '💎', '💵', '💸', '🪙', '💹'
            },
            'data_visualization': {
                '📊', '📈', '📉', '📋', '📄', '📁', '📂'
            },
            'user_interaction': {
                '⚙', '🔧', '🔍', '👁', '🗑', '📝', '✏'
            },
            'achievement_system': {
                '🏆', '🏅', '🥇', '🥈', '🥉', '👑'
            },
            'security_permissions': {
                '🔒', '🔐', '🛡', '🚫', '🔑'
            }
        }

    def scan_panel_files(self):
        """Scan all panel files for emoji usage"""

        # Scan embed files
        embed_files = list(self.root_path.glob('src/cogs/*/panel/embeds/*.py'))
        for file_path in embed_files:
            if file_path.name != '__init__.py':
                self._analyze_file(file_path, 'embed')

        # Scan component files
        component_files = list(self.root_path.glob('src/cogs/*/panel/components/*.py'))
        for file_path in component_files:
            if file_path.name != '__init__.py':
                self._analyze_file(file_path, 'component')

        print(f"Scanned {len(embed_files)} embed files and {len(component_files)} component files")
        print(f"Found {len(self.emoji_usages)} emoji usage instances")

    def _analyze_file(self, file_path: Path, file_type: str):
        """Analyze individual file for emoji usage"""
        try:
            with open(file_path, encoding='utf-8') as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, 1):
                emojis_found = self._extract_emojis(line)
                for emoji in emojis_found:
                    context_type = self._determine_context_type(line, file_type)

                    self.emoji_usages.append(EmojiUsage(
                        emoji=emoji,
                        file_path=str(file_path.relative_to(self.root_path)),
                        line_number=line_num,
                        line_content=line.strip(),
                        context_type=context_type
                    ))

        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")

    def _extract_emojis(self, text: str) -> list[str]:
        """Extract Unicode emojis from text"""
        emoji_pattern = re.compile(
            r'[\U0001F600-\U0001F64F]|'  # emoticons
            r'[\U0001F300-\U0001F5FF]|'  # symbols & pictographs
            r'[\U0001F680-\U0001F6FF]|'  # transport & map
            r'[\U0001F1E0-\U0001F1FF]|'  # regional indicators
            r'[\U00002600-\U000026FF]|'  # misc symbols
            r'[\U00002700-\U000027BF]|'  # dingbats
            r'[\U0001F900-\U0001F9FF]|'  # supplemental symbols
            r'[\U0001FA70-\U0001FAFF]'   # symbols and pictographs extended-A
        )

        return emoji_pattern.findall(text)

    def _determine_context_type(self, line: str, file_type: str) -> str:
        """Determine the context type of emoji usage"""
        line_lower = line.lower().strip()

        # Context patterns
        if 'title=' in line_lower:
            return 'embed_title'
        elif 'name=' in line_lower and ('field' in line_lower or 'add_field' in line_lower):
            return 'embed_field_name'
        elif 'value=' in line_lower and 'field' in line_lower:
            return 'embed_field_value'
        elif 'label=' in line_lower and 'button' in file_type:
            return 'button_label'
        elif 'emoji=' in line_lower:
            return 'button_emoji'
        elif 'description=' in line_lower:
            return 'description'
        elif 'placeholder=' in line_lower:
            return 'placeholder'
        else:
            return 'general'

    def analyze_emojis(self) -> dict[str, EmojiAnalysis]:
        """Analyze all found emojis and classify them"""
        emoji_stats = {}

        # Group usages by emoji
        for usage in self.emoji_usages:
            if usage.emoji not in emoji_stats:
                emoji_stats[usage.emoji] = []
            emoji_stats[usage.emoji].append(usage)

        # Analyze each emoji
        analyses = {}
        for emoji, usages in emoji_stats.items():
            analysis = self._analyze_single_emoji(emoji, usages)
            analyses[emoji] = analysis

        return analyses

    def _analyze_single_emoji(self, emoji: str, usages: list[EmojiUsage]) -> EmojiAnalysis:
        """Analyze a single emoji's usage patterns"""

        # Collect statistics
        usage_count = len(usages)
        files_used = list(set(usage.file_path for usage in usages))
        contexts = list(set(usage.context_type for usage in usages))

        # Determine if functional
        is_functional = self._is_functional_emoji(emoji, usages)

        # Generate purpose description
        purpose_description = self._describe_emoji_purpose(emoji, usages, is_functional)

        # Make recommendation
        if is_functional:
            recommendation = 'KEEP'
            reasoning = 'Essential for user interface functionality'
        elif usage_count >= 10:  # High usage decorative might be worth keeping
            recommendation = 'REVIEW'
            reasoning = 'High usage frequency - consider user feedback'
        else:
            recommendation = 'REMOVE'
            reasoning = 'Decorative usage with minimal functional value'

        return EmojiAnalysis(
            emoji=emoji,
            usage_count=usage_count,
            files_used=files_used,
            contexts=contexts,
            is_functional=is_functional,
            purpose_description=purpose_description,
            recommendation=recommendation,
            reasoning=reasoning
        )

    def _is_functional_emoji(self, emoji: str, usages: list[EmojiUsage]) -> bool:
        """Determine if an emoji serves a functional purpose"""

        # Check against functional patterns
        for pattern_type, emoji_set in self.functional_patterns.items():
            if emoji in emoji_set:
                return True

        # Check context-based functionality
        functional_contexts = {'button_emoji', 'embed_field_name'}
        context_functionality = any(
            usage.context_type in functional_contexts
            for usage in usages
        )

        # Check for status or system-related usage
        system_keywords = ['status', 'error', 'success', 'warning', 'config', 'setting']
        system_usage = any(
            any(keyword in usage.line_content.lower() for keyword in system_keywords)
            for usage in usages
        )

        return context_functionality or system_usage

    def _describe_emoji_purpose(self, emoji: str, usages: list[EmojiUsage], is_functional: bool) -> str:
        """Generate a description of the emoji's purpose"""

        if is_functional:
            # Try to identify specific functional purpose
            for pattern_type, emoji_set in self.functional_patterns.items():
                if emoji in emoji_set:
                    return f"Functional - {pattern_type.replace('_', ' ')}"

        # Analyze usage contexts to infer purpose
        context_types = [usage.context_type for usage in usages]
        most_common_context = max(set(context_types), key=context_types.count)

        if most_common_context == 'embed_title':
            return "Title decoration and branding"
        elif most_common_context == 'button_label':
            return "Button labeling and user guidance"
        elif most_common_context == 'embed_field_name':
            return "Section headers and organization"
        else:
            return "General decorative usage"

    def generate_text_report(self, analyses: dict[str, EmojiAnalysis]) -> str:
        """Generate a comprehensive text-based report"""

        # Sort by recommendation and usage count
        keep_emojis = {k: v for k, v in analyses.items() if v.recommendation == 'KEEP'}
        review_emojis = {k: v for k, v in analyses.items() if v.recommendation == 'REVIEW'}
        remove_emojis = {k: v for k, v in analyses.items() if v.recommendation == 'REMOVE'}

        report = []
        report.append("# Discord ROAS Bot - Emoji Usage Analysis Report")
        report.append("## Story 1.1: emoji-audit-and-categorization")
        report.append("")
        report.append(f"**Analysis Date**: {self._get_current_date()}")
        report.append(f"**Total Emoji Instances**: {len(self.emoji_usages)}")
        report.append(f"**Unique Emojis Found**: {len(analyses)}")
        report.append("")

        # Summary statistics
        report.append("## Executive Summary")
        report.append("")
        report.append(f"- **KEEP (Functional)**: {len(keep_emojis)} emojis")
        report.append(f"- **REVIEW (High Usage)**: {len(review_emojis)} emojis")
        report.append(f"- **REMOVE (Decorative)**: {len(remove_emojis)} emojis")
        report.append("")

        # Detailed sections
        self._add_emoji_section(report, "FUNCTIONAL EMOJIS - RECOMMENDED TO KEEP", keep_emojis)
        self._add_emoji_section(report, "HIGH USAGE EMOJIS - REQUIRES REVIEW", review_emojis)
        self._add_emoji_section(report, "DECORATIVE EMOJIS - RECOMMENDED FOR REMOVAL", remove_emojis)

        # Technical details
        report.append("## Technical Analysis Details")
        report.append("")
        report.append("### Files Analyzed")
        files_scanned = set(usage.file_path for usage in self.emoji_usages)
        for file_path in sorted(files_scanned):
            report.append(f"- {file_path}")
        report.append("")

        report.append("### Context Type Distribution")
        context_counts = {}
        for usage in self.emoji_usages:
            context_counts[usage.context_type] = context_counts.get(usage.context_type, 0) + 1

        for context, count in sorted(context_counts.items(), key=lambda x: x[1], reverse=True):
            report.append(f"- {context}: {count} instances")
        report.append("")

        return "\n".join(report)

    def _add_emoji_section(self, report: list[str], title: str, emojis: dict[str, EmojiAnalysis]):
        """Add a section for specific emoji category"""
        report.append(f"## {title}")
        report.append("")

        if not emojis:
            report.append("None found.")
            report.append("")
            return

        # Sort by usage count (highest first)
        sorted_emojis = sorted(emojis.items(), key=lambda x: x[1].usage_count, reverse=True)

        for emoji, analysis in sorted_emojis:
            report.append(f"### {emoji}")
            report.append(f"- **Usage Count**: {analysis.usage_count}")
            report.append(f"- **Files Used**: {len(analysis.files_used)}")
            report.append(f"- **Purpose**: {analysis.purpose_description}")
            report.append(f"- **Recommendation**: {analysis.recommendation}")
            report.append(f"- **Reasoning**: {analysis.reasoning}")

            # Show contexts if interesting
            if len(analysis.contexts) > 1:
                report.append(f"- **Contexts**: {', '.join(analysis.contexts)}")

            report.append("")

    def _get_current_date(self) -> str:
        """Get current date in readable format"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def main():
    """Main execution function"""

    # Initialize tool
    root_path = Path.cwd()
    tool = EmojiAuditTool(str(root_path))

    print("Starting Discord ROAS Bot Emoji Audit...")
    print("=" * 50)

    # Step 1: Scan all panel files
    print("\n1. Scanning panel components...")
    tool.scan_panel_files()

    # Step 2: Analyze emoji usage patterns
    print("\n2. Analyzing emoji usage patterns...")
    analyses = tool.analyze_emojis()

    # Step 3: Generate comprehensive report
    print("\n3. Generating analysis report...")
    report_content = tool.generate_text_report(analyses)

    # Save report
    report_path = root_path / 'emoji_analysis_report.md'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_content)

    print(f"\nReport saved to: {report_path}")

    # Summary for user
    keep_count = sum(1 for a in analyses.values() if a.recommendation == 'KEEP')
    review_count = sum(1 for a in analyses.values() if a.recommendation == 'REVIEW')
    remove_count = sum(1 for a in analyses.values() if a.recommendation == 'REMOVE')

    print("\n" + "=" * 50)
    print("ANALYSIS COMPLETE")
    print("=" * 50)
    print(f"Functional emojis to KEEP: {keep_count}")
    print(f"Emojis requiring REVIEW: {review_count}")
    print(f"Decorative emojis to REMOVE: {remove_count}")
    print(f"\nTotal emojis analyzed: {len(analyses)}")
    print(f"Total usage instances: {len(tool.emoji_usages)}")


if __name__ == "__main__":
    main()
