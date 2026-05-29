// lib/screens/slip_builder_screen.dart

import 'package:flutter/material.dart';

import '../models/slip_pick.dart';
import '../services/slip_builder_service.dart';

class SlipBuilderScreen extends StatefulWidget {
  const SlipBuilderScreen({
    super.key,
  });

  @override
  State<SlipBuilderScreen> createState() => _SlipBuilderScreenState();
}

class _SlipBuilderScreenState extends State<SlipBuilderScreen> {
  final SlipBuilderService _service = SlipBuilderService.instance;

  bool _jackpotMode = false;

  @override
  void initState() {
    super.initState();
    _service.addListener(_onSlipChanged);
  }

  @override
  void dispose() {
    _service.removeListener(_onSlipChanged);
    super.dispose();
  }

  void _onSlipChanged() {
    if (!mounted) return;
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final items = _service.items;

    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FB),
      appBar: AppBar(
        title: const Text('Slip Builder'),
        backgroundColor: const Color(0xFF0F172A),
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            tooltip: 'Clear slip',
            onPressed: items.isEmpty ? null : _service.clear,
            icon: const Icon(Icons.delete_outline),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _ModeToggle(
            jackpotMode: _jackpotMode,
            onChanged: (value) {
              setState(() {
                _jackpotMode = value;
              });
            },
          ),
          const SizedBox(height: 16),
          _SlipSummary(
            count: _service.count,
            totalOdds: _service.totalOdds,
            averageConfidence: _service.averageConfidence,
            averageExecutionScore: _service.averageExecutionScore,
            averageSurvivability: _service.averageSurvivability,
            riskLevel: _service.riskLevel,
            jackpotMode: _jackpotMode,
          ),
          const SizedBox(height: 16),
          if (items.isEmpty)
            const _EmptySlip()
          else
            ...items.asMap().entries.map(
                  (entry) => _SlipPickCard(
                    pick: entry.value,
                    jackpotMode: _jackpotMode,
                    onRemove: () => _service.removeAt(entry.key),
                  ),
                ),
        ],
      ),
    );
  }
}

class _ModeToggle extends StatelessWidget {
  final bool jackpotMode;
  final ValueChanged<bool> onChanged;

  const _ModeToggle({
    required this.jackpotMode,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(6),
      decoration: BoxDecoration(
        color: const Color(0xFFF1F5F9),
        borderRadius: BorderRadius.circular(18),
      ),
      child: Row(
        children: [
          Expanded(
            child: _ModeButton(
              title: 'Normal Slip',
              subtitle: 'Any market',
              icon: Icons.receipt_long_outlined,
              selected: !jackpotMode,
              onTap: () => onChanged(false),
            ),
          ),
          const SizedBox(width: 6),
          Expanded(
            child: _ModeButton(
              title: 'Jackpot Slip',
              subtitle: '1X2 focus',
              icon: Icons.casino_outlined,
              selected: jackpotMode,
              onTap: () => onChanged(true),
            ),
          ),
        ],
      ),
    );
  }
}

class _ModeButton extends StatelessWidget {
  final String title;
  final String subtitle;
  final IconData icon;
  final bool selected;
  final VoidCallback onTap;

  const _ModeButton({
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final color = selected ? const Color(0xFF2563EB) : Colors.black54;

    return InkWell(
      borderRadius: BorderRadius.circular(14),
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: selected ? Colors.white : Colors.transparent,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: selected
                ? const Color(0xFF2563EB).withOpacity(0.25)
                : Colors.transparent,
          ),
        ),
        child: Row(
          children: [
            Icon(icon, color: color),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: TextStyle(
                      color: color,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  Text(
                    subtitle,
                    style: TextStyle(
                      color: selected ? Colors.black54 : Colors.black38,
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SlipSummary extends StatelessWidget {
  final int count;
  final double totalOdds;
  final double? averageConfidence;
  final double? averageExecutionScore;
  final double? averageSurvivability;
  final String riskLevel;
  final bool jackpotMode;

  const _SlipSummary({
    required this.count,
    required this.totalOdds,
    required this.averageConfidence,
    required this.averageExecutionScore,
    required this.averageSurvivability,
    required this.riskLevel,
    required this.jackpotMode,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF0F172A),
        borderRadius: BorderRadius.circular(24),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            jackpotMode ? 'Jackpot Slip Summary' : 'Slip Summary',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: Colors.white,
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: _SummaryMetric(
                  label: 'Picks',
                  value: count.toString(),
                ),
              ),
              Expanded(
                child: _SummaryMetric(
                  label: 'Total Odds',
                  value: count == 0 ? '—' : totalOdds.toStringAsFixed(2),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: _SummaryMetric(
                  label: 'Avg Conf',
                  value: _percentText(averageConfidence),
                ),
              ),
              Expanded(
                child: _SummaryMetric(
                  label: 'Risk',
                  value: riskLevel,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: _SummaryMetric(
                  label: 'Execution',
                  value: _scoreText(averageExecutionScore),
                ),
              ),
              Expanded(
                child: _SummaryMetric(
                  label: 'Survivability',
                  value: _scoreText(averageSurvivability),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _SummaryMetric extends StatelessWidget {
  final String label;
  final String value;

  const _SummaryMetric({
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(right: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.08),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.w900,
              fontSize: 18,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: const TextStyle(
              color: Colors.white70,
              fontWeight: FontWeight.w600,
              fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }
}

class _SlipPickCard extends StatelessWidget {
  final SlipPick pick;
  final bool jackpotMode;
  final VoidCallback onRemove;

  const _SlipPickCard({
    required this.pick,
    required this.jackpotMode,
    required this.onRemove,
  });

  @override
  Widget build(BuildContext context) {
    final confidence = _percentText(pick.confidence);
    final odds = pick.odds == null ? '—' : pick.odds!.toStringAsFixed(2);

    final isJackpotFriendly = _isJackpotFriendlyMarket(pick.market);

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: jackpotMode && !isJackpotFriendly
            ? const Color(0xFFFFFBEB)
            : Colors.white,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(
          color: jackpotMode && !isJackpotFriendly
              ? const Color(0xFF92400E).withOpacity(0.22)
              : Colors.black.withOpacity(0.06),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.sports_soccer, color: Color(0xFF2563EB)),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  pick.matchTitle,
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                ),
              ),
              IconButton(
                onPressed: onRemove,
                icon: const Icon(Icons.close),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            '${pick.league} · ${pick.kickoff}',
            style: const TextStyle(
              color: Colors.black54,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: _PickMainBox(
                  label: 'Market',
                  value: _marketLabel(pick.market),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _PickMainBox(
                  label: 'Selection',
                  value: _marketLabel(pick.selection),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(child: _MiniMetric(label: 'Confidence', value: confidence)),
              Expanded(child: _MiniMetric(label: 'Odds', value: odds)),
              Expanded(child: _MiniMetric(label: 'Kenya', value: pick.kenyaGrade)),
            ],
          ),
          const SizedBox(height: 10),
          _DetailRow(label: 'Bookmaker', value: pick.bookmaker),
          _DetailRow(label: 'Locality', value: pick.bookmakerLocality),
          _DetailRow(
            label: 'Execution',
            value: _scoreText(pick.executionScore),
          ),
          _DetailRow(
            label: 'Survivability',
            value: _scoreText(pick.survivabilityScore),
          ),
          if (jackpotMode && !isJackpotFriendly) ...[
            const SizedBox(height: 10),
            const _WarningBox(
              text:
                  'This pick is not a jackpot pick. Jackpot slips only allow Home Win (1), Draw (X), or Away Win (2).'            ),
          ],
        ],
      ),
    );
  }
}

class _PickMainBox extends StatelessWidget {
  final String label;
  final String value;

  const _PickMainBox({
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(13),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            value,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              fontWeight: FontWeight.w900,
              color: Color(0xFF0F172A),
            ),
          ),
          const SizedBox(height: 4),
          Text(
            label,
            style: const TextStyle(
              color: Colors.black54,
              fontWeight: FontWeight.w700,
              fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }
}

class _MiniMetric extends StatelessWidget {
  final String label;
  final String value;

  const _MiniMetric({
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(right: 8),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: const TextStyle(
              color: Colors.black54,
              fontSize: 11,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

class _DetailRow extends StatelessWidget {
  final String label;
  final String value;

  const _DetailRow({
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    if (value == '—' || value.trim().isEmpty) {
      return const SizedBox.shrink();
    }

    return Padding(
      padding: const EdgeInsets.only(top: 7),
      child: Row(
        children: [
          SizedBox(
            width: 110,
            child: Text(
              label,
              style: const TextStyle(
                color: Colors.black54,
                fontWeight: FontWeight.w700,
                fontSize: 12,
              ),
            ),
          ),
          Expanded(
            child: Text(
              _marketLabel(value),
              style: const TextStyle(
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _WarningBox extends StatelessWidget {
  final String text;

  const _WarningBox({
    required this.text,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(11),
      decoration: BoxDecoration(
        color: const Color(0xFFFFFBEB),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: const Color(0xFF92400E).withOpacity(0.18),
        ),
      ),
      child: Text(
        text,
        style: const TextStyle(
          color: Color(0xFF92400E),
          fontWeight: FontWeight.w800,
          fontSize: 12,
        ),
      ),
    );
  }
}

class _EmptySlip extends StatelessWidget {
  const _EmptySlip();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(
          color: Colors.black.withOpacity(0.06),
        ),
      ),
      child: Column(
        children: [
          const Icon(
            Icons.playlist_add,
            size: 46,
            color: Colors.black38,
          ),
          const SizedBox(height: 10),
          Text(
            'No picks in slip yet',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w900,
                ),
          ),
          const SizedBox(height: 4),
          const Text(
            'Open Match Intelligence and add picks from Market Alternatives.',
            textAlign: TextAlign.center,
            style: TextStyle(color: Colors.black54),
          ),
        ],
      ),
    );
  }
}

bool _isJackpotFriendlyMarket(String market) {
  final lower = market.toLowerCase();

  return lower == 'home_win' ||
      lower == 'draw' ||
      lower == 'away_win';
}

String _percentText(double? value) {
  if (value == null) return '—';

  if (value <= 1) {
    return '${(value * 100).toStringAsFixed(1)}%';
  }

  return '${value.toStringAsFixed(1)}%';
}

String _scoreText(double? value) {
  if (value == null) return '—';

  if (value <= 1) {
    return '${(value * 100).toStringAsFixed(1)}%';
  }

  return value.toStringAsFixed(2);
}

String _marketLabel(String value) {
  final clean = value.trim();

  if (clean.isEmpty || clean == '—') {
    return clean.isEmpty ? '—' : clean;
  }

  const labels = {
    'home_win': 'Home Win',
    'draw': 'Draw',
    'away_win': 'Away Win',
    'over_1_5_goals': 'Over 1.5 Goals',
    'over_2_5_goals': 'Over 2.5 Goals',
    'over_3_5_goals': 'Over 3.5 Goals',
    'under_1_5_goals': 'Under 1.5 Goals',
    'under_2_5_goals': 'Under 2.5 Goals',
    'under_3_5_goals': 'Under 3.5 Goals',
    'btts_yes': 'BTTS Yes',
    'btts_no': 'BTTS No',
    'double_chance_1x': 'Double Chance 1X',
    'double_chance_x2': 'Double Chance X2',
    'double_chance_12': 'Double Chance 12',
    'not_home_win': 'Not Home Win',
    'not_draw': 'Not Draw',
    'not_away_win': 'Not Away Win',
    'over_1_5': 'Over 1.5',
    'over_2_5': 'Over 2.5',
    'over_3_5': 'Over 3.5',
    'under_1_5': 'Under 1.5',
    'under_2_5': 'Under 2.5',
    'under_3_5': 'Under 3.5',
    'jackpot_1x2': 'Jackpot 1X2',
    '1': 'Home Win (1)',
    'X': 'Draw (X)',
    '2': 'Away Win (2)',
  };

  final lower = clean.toLowerCase();

  if (labels.containsKey(lower)) {
    return labels[lower]!;
  }

  return clean
      .replaceAll('_', ' ')
      .split(' ')
      .where((part) => part.trim().isNotEmpty)
      .map((part) {
    if (part.length <= 2) return part.toUpperCase();
    return '${part[0].toUpperCase()}${part.substring(1)}';
  }).join(' ');
}