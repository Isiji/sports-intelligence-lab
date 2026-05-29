// lib/screens/group_details_screen.dart

import 'package:flutter/material.dart';

import '../models/group_dashboard_item.dart';
import 'match_intelligence_screen.dart';

class GroupDetailsScreen extends StatelessWidget {
  final GroupDashboardSummary group;

  const GroupDetailsScreen({
    super.key,
    required this.group,
  });

  void _openMatch(BuildContext context, GroupDashboardItem item) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => MatchIntelligenceScreen(matchId: item.matchId),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final riskColor = _riskColor(group.riskLevel);

    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FB),
      appBar: AppBar(
        title: Text(group.groupName),
        backgroundColor: const Color(0xFF0F172A),
        foregroundColor: Colors.white,
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _SummaryCard(group: group, riskColor: riskColor),
            const SizedBox(height: 16),
            _SectionTitle(
              title: 'Group Picks',
              subtitle: 'Each pick includes odds, confidence and execution intelligence.',
            ),
            const SizedBox(height: 12),
            ...group.picks.map(
              (item) => _PickCard(
                item: item,
                onOpenMatch: () => _openMatch(context, item),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SummaryCard extends StatelessWidget {
  final GroupDashboardSummary group;
  final Color riskColor;

  const _SummaryCard({
    required this.group,
    required this.riskColor,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF0F172A), Color(0xFF1E3A8A)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(26),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _Pill(text: group.riskLevel, color: riskColor),
          const SizedBox(height: 12),
          Text(
            group.groupName,
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  color: Colors.white,
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(child: _DarkMetric(label: 'Picks', value: '${group.size}')),
              const SizedBox(width: 10),
              Expanded(
                child: _DarkMetric(
                  label: 'Total Odds',
                  value: group.totalOdds == 0.0 ? '—' : group.totalOdds.toStringAsFixed(2),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _DarkMetric(
                  label: 'Ready',
                  value: '${group.executionReadyCount}/${group.size}',
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: _DarkMetric(
                  label: 'Avg Conf',
                  value: '${(group.avgConfidence * 100).toStringAsFixed(1)}%',
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _DarkMetric(
                  label: 'Execution',
                  value: group.avgExecutionScore.toStringAsFixed(2),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _DarkMetric(
                  label: 'Survivability',
                  value: group.avgSurvivability.toStringAsFixed(2),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _PickCard extends StatelessWidget {
  final GroupDashboardItem item;
  final VoidCallback onOpenMatch;

  const _PickCard({
    required this.item,
    required this.onOpenMatch,
  });

  @override
  Widget build(BuildContext context) {
    final readyColor =
        item.executionReady ? const Color(0xFF166534) : const Color(0xFF92400E);

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: Colors.black.withOpacity(0.06)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                item.executionReady
                    ? Icons.check_circle_outline
                    : Icons.warning_amber_rounded,
                color: readyColor,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  item.league,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: Colors.black54,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              Text(
                item.confidenceText,
                style: const TextStyle(
                  fontWeight: FontWeight.w900,
                  color: Color(0xFF0F172A),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            '${item.homeTeam} vs ${item.awayTeam}',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 4),
          Text(
            item.kickoffEat,
            style: const TextStyle(
              color: Colors.black54,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(child: _Metric(label: 'Market', value: _label(item.market))),
              Expanded(child: _Metric(label: 'Pick', value: _label(item.predictedLabel))),
              Expanded(child: _Metric(label: 'Odds', value: item.oddsText)),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(child: _Metric(label: 'Execution', value: item.executionScoreText)),
              Expanded(child: _Metric(label: 'Survivability', value: item.survivabilityText)),
              Expanded(child: _Metric(label: 'Local', value: item.localRealismText)),
            ],
          ),
          const SizedBox(height: 10),
          _InfoRow(label: 'Execution market', value: _label(item.executionMarket)),
          _InfoRow(label: 'Execution selection', value: _label(item.executionSelection)),
          _InfoRow(label: 'Bookmaker', value: item.oddsBookmaker),
          _InfoRow(label: 'Locality', value: item.bookmakerLocality),
          if (item.executionReasons.isNotEmpty) ...[
            const SizedBox(height: 8),
            ...item.executionReasons.take(4).map((reason) => _ReasonText(text: reason)),
          ],
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: onOpenMatch,
              icon: const Icon(Icons.analytics_outlined),
              label: const Text('Open Match Intelligence'),
            ),
          ),
        ],
      ),
    );
  }
}

class _DarkMetric extends StatelessWidget {
  final String label;
  final String value;

  const _DarkMetric({
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.13),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white.withOpacity(0.16)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            value == '—' ? 'Unknown' : value,
            style: const TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.w900,
              fontSize: 16,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: TextStyle(
              color: Colors.white.withOpacity(0.72),
              fontWeight: FontWeight.w700,
              fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }
}

class _Metric extends StatelessWidget {
  final String label;
  final String value;

  const _Metric({
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    final clean = value == '—' ? 'Unknown' : value;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          clean,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(
            fontWeight: FontWeight.w900,
            color: Color(0xFF0F172A),
          ),
        ),
        const SizedBox(height: 2),
        Text(
          label,
          style: const TextStyle(
            color: Colors.black54,
            fontSize: 12,
            fontWeight: FontWeight.w700,
          ),
        ),
      ],
    );
  }
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;

  const _InfoRow({
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    if (value == '—' || value.trim().isEmpty) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.only(bottom: 5),
      child: Row(
        children: [
          SizedBox(
            width: 130,
            child: Text(
              label,
              style: const TextStyle(
                color: Colors.black54,
                fontSize: 12,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(
                color: Colors.black87,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ReasonText extends StatelessWidget {
  final String text;

  const _ReasonText({
    required this.text,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: const Color(0xFFFFFBEB),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFF92400E).withOpacity(0.18)),
      ),
      child: Text(
        text,
        style: const TextStyle(
          color: Color(0xFF92400E),
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class _Pill extends StatelessWidget {
  final String text;
  final Color color;

  const _Pill({
    required this.text,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(
        color: color.withOpacity(0.10),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withOpacity(0.25)),
      ),
      child: Text(
        text,
        style: TextStyle(
          color: color,
          fontSize: 12,
          fontWeight: FontWeight.w900,
        ),
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  final String title;
  final String subtitle;

  const _SectionTitle({
    required this.title,
    required this.subtitle,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.w900,
              ),
        ),
        const SizedBox(height: 4),
        Text(
          subtitle,
          style: const TextStyle(
            color: Colors.black54,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
  }
}

Color _riskColor(String risk) {
  switch (risk.toUpperCase()) {
    case 'LOW':
      return const Color(0xFF166534);
    case 'MEDIUM':
      return const Color(0xFF92400E);
    default:
      return const Color(0xFF9F1239);
  }
}

String _label(String value) {
  if (value == '—') return value;

  return value
      .replaceAll('_', ' ')
      .split(' ')
      .where((part) => part.trim().isNotEmpty)
      .map((part) {
    if (part.length <= 2) return part.toUpperCase();
    return '${part[0].toUpperCase()}${part.substring(1)}';
  }).join(' ');
}