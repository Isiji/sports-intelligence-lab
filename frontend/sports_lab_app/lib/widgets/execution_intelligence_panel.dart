// lib/widgets/execution_intelligence_panel.dart

import 'package:flutter/material.dart';

import '../models/match_intelligence.dart';

class ExecutionIntelligencePanel extends StatelessWidget {
  final PredictionPick pick;

  const ExecutionIntelligencePanel({
    super.key,
    required this.pick,
  });

  @override
  Widget build(BuildContext context) {
    final executionReady = _cleanBoolText(pick.executionReady);
    final executionScore = _scoreText(pick.executionScore);
    final survivabilityScore = _scoreText(pick.survivabilityScore);
    final localRealismScore = _scoreText(pick.localRealismScore);

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(
          color: Colors.black.withOpacity(0.06),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _ExecutionReadyBanner(
            executionReady: executionReady,
            timingRisk: pick.timingRisk,
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: _ExecutionMetricCard(
                  icon: Icons.speed_outlined,
                  label: 'Execution Score',
                  value: executionScore,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _ExecutionMetricCard(
                  icon: Icons.shield_outlined,
                  label: 'Survivability',
                  value: survivabilityScore,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: _ExecutionMetricCard(
                  icon: Icons.location_on_outlined,
                  label: 'Local Realism',
                  value: localRealismScore,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _ExecutionMetricCard(
                  icon: Icons.timer_outlined,
                  label: 'Timing Risk',
                  value: pick.timingRisk,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          _ExecutionDetailsCard(pick: pick),
          if (pick.marketAlternatives.isNotEmpty) ...[
            const SizedBox(height: 14),
            _MarketAlternativesCard(
              alternatives: pick.marketAlternatives,
            ),
          ],
        ],
      ),
    );
  }
}

class _ExecutionReadyBanner extends StatelessWidget {
  final String executionReady;
  final String timingRisk;

  const _ExecutionReadyBanner({
    required this.executionReady,
    required this.timingRisk,
  });

  @override
  Widget build(BuildContext context) {
    final ready = executionReady.toLowerCase();
    final risky = timingRisk.toLowerCase();

    final isReady = ready == 'yes' ||
        ready == 'true' ||
        ready == 'ready' ||
        ready == '1';

    final isRisky = risky.contains('high') ||
        risky.contains('danger') ||
        risky.contains('late') ||
        risky.contains('avoid');

    final color = isReady && !isRisky
        ? const Color(0xFF166534)
        : isRisky
            ? const Color(0xFF9F1239)
            : const Color(0xFF92400E);

    final background = isReady && !isRisky
        ? const Color(0xFFECFDF5)
        : isRisky
            ? const Color(0xFFFFF1F2)
            : const Color(0xFFFFFBEB);

    final text = isReady && !isRisky
        ? 'Execution looks usable'
        : isRisky
            ? 'Execution needs caution'
            : 'Execution readiness unclear';

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(13),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: color.withOpacity(0.25),
        ),
      ),
      child: Row(
        children: [
          Icon(
            isReady && !isRisky
                ? Icons.check_circle_outline
                : Icons.warning_amber_rounded,
            color: color,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              text,
              style: TextStyle(
                color: color,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
          _SmallPill(
            text: executionReady == '—' ? 'Unknown' : executionReady,
            color: color,
          ),
        ],
      ),
    );
  }
}

class _ExecutionMetricCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;

  const _ExecutionMetricCard({
    required this.icon,
    required this.label,
    required this.value,
  });

  @override
  Widget build(BuildContext context) {
    final cleanValue = value == '—' ? 'Unknown' : value;

    return Container(
      constraints: const BoxConstraints(
        minHeight: 108,
      ),
      padding: const EdgeInsets.all(13),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: Colors.black.withOpacity(0.05),
        ),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            icon,
            color: const Color(0xFF2563EB),
          ),
          const SizedBox(height: 22),
          Text(
            cleanValue,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              fontWeight: FontWeight.w900,
              fontSize: 17,
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
      ),
    );
  }
}

class _ExecutionDetailsCard extends StatelessWidget {
  final PredictionPick pick;

  const _ExecutionDetailsCard({
    required this.pick,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(13),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: Colors.black.withOpacity(0.05),
        ),
      ),
      child: Column(
        children: [
          _DetailRow(
            label: 'Execution market',
            value: pick.executionMarket,
          ),
          _DetailRow(
            label: 'Execution selection',
            value: pick.executionSelection,
          ),
          _DetailRow(
            label: 'Bookmaker',
            value: pick.bookmaker,
          ),
          _DetailRow(
            label: 'Bookmaker locality',
            value: pick.bookmakerLocality,
          ),
          _DetailRow(
            label: 'Kenyan availability',
            value: pick.kenyanAvailability,
          ),
          _DetailRow(
            label: 'Odds',
            value: pick.odds == null ? '—' : pick.odds!.toStringAsFixed(2),
          ),
          _DetailRow(
            label: 'Value score',
            value: pick.valueScore == null
                ? '—'
                : pick.valueScore!.toStringAsFixed(3),
          ),
        ],
      ),
    );
  }
}

class _MarketAlternativesCard extends StatelessWidget {
  final List<dynamic> alternatives;

  const _MarketAlternativesCard({
    required this.alternatives,
  });

  @override
  Widget build(BuildContext context) {
    final items = alternatives.take(6).toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Market Alternatives',
          style: TextStyle(
            fontWeight: FontWeight.w900,
            color: Colors.black87,
          ),
        ),
        const SizedBox(height: 8),
        ...items.map(
          (item) => _AlternativeRow(item: item),
        ),
      ],
    );
  }
}

class _AlternativeRow extends StatelessWidget {
  final dynamic item;

  const _AlternativeRow({
    required this.item,
  });

  @override
  Widget build(BuildContext context) {
    final map = item is Map ? item as Map : const {};

    final market = _stringValue([
      map['market'],
      map['execution_market'],
      map['pick'],
      map['recommended_pick'],
      item is String ? item : null,
    ]);

    final selection = _stringValue([
      map['selection'],
      map['execution_selection'],
      map['label'],
      map['recommended_label'],
      map['predicted_label'],
    ]);

    final confidence = _doubleValue([
      map['confidence'],
      map['probability'],
      map['score'],
    ]);

    final odds = _doubleValue([
      map['odds'],
      map['best_odds'],
      map['execution_odds'],
    ]);

    final rightText = confidence != null
        ? '${_percentText(confidence)} conf'
        : odds != null
            ? '${odds.toStringAsFixed(2)} odds'
            : 'Alternative';

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(11),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(15),
        border: Border.all(
          color: Colors.black.withOpacity(0.05),
        ),
      ),
      child: Row(
        children: [
          const Icon(
            Icons.alt_route_outlined,
            color: Color(0xFF2563EB),
            size: 18,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              selection == '—'
                  ? _marketLabel(market)
                  : '${_marketLabel(market)} · ${_marketLabel(selection)}',
              style: const TextStyle(
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
          Text(
            rightText,
            style: const TextStyle(
              fontWeight: FontWeight.w900,
              color: Color(0xFF0F172A),
              fontSize: 12,
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
    if (value == '—') return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.only(bottom: 9),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 135,
            child: Text(
              label,
              style: const TextStyle(
                color: Colors.black54,
                fontWeight: FontWeight.w800,
                fontSize: 12,
              ),
            ),
          ),
          Expanded(
            child: Text(
              _marketLabel(value),
              style: const TextStyle(
                color: Color(0xFF0F172A),
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SmallPill extends StatelessWidget {
  final String text;
  final Color color;

  const _SmallPill({
    required this.text,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: 9,
        vertical: 6,
      ),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.75),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        _marketLabel(text),
        style: TextStyle(
          color: color,
          fontWeight: FontWeight.w900,
          fontSize: 12,
        ),
      ),
    );
  }
}

String _cleanBoolText(String value) {
  final clean = value.trim().toLowerCase();

  if (clean == 'true' || clean == '1' || clean == 'yes') {
    return 'Ready';
  }

  if (clean == 'false' || clean == '0' || clean == 'no') {
    return 'Not Ready';
  }

  if (value.trim().isEmpty) {
    return '—';
  }

  return value;
}

String _scoreText(double? value) {
  if (value == null) return '—';

  if (value <= 1) {
    return '${(value * 100).toStringAsFixed(1)}%';
  }

  return value.toStringAsFixed(2);
}

String _percentText(double value) {
  if (value <= 1) {
    return '${(value * 100).toStringAsFixed(1)}%';
  }

  return '${value.toStringAsFixed(1)}%';
}

String _stringValue(List<dynamic> values) {
  for (final value in values) {
    if (value == null) continue;

    final text = value.toString().trim();

    if (text.isNotEmpty && text.toLowerCase() != 'null') {
      return text;
    }
  }

  return '—';
}

double? _doubleValue(List<dynamic> values) {
  for (final value in values) {
    if (value == null) continue;

    if (value is num) {
      return value.toDouble();
    }

    final parsed = double.tryParse(value.toString());
    if (parsed != null) {
      return parsed;
    }
  }

  return null;
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
    'under_2_5_goals': 'Under 2.5 Goals',
    'btts_yes': 'BTTS Yes',
    'btts_no': 'BTTS No',
    'double_chance_1x': 'Double Chance 1X',
    'double_chance_x2': 'Double Chance X2',
    'double_chance_12': 'Double Chance 12',
    '1x': 'Double Chance 1X',
    'x2': 'Double Chance X2',
    '12': 'Double Chance 12',
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