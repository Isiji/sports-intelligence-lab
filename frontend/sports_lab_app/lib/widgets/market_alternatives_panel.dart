// lib/widgets/market_alternatives_panel.dart

import 'package:flutter/material.dart';

import '../models/match_intelligence.dart';

class MarketAlternativesPanel extends StatelessWidget {
  final bool isLoading;
  final String? error;
  final List<MarketAlternative> markets;
  final VoidCallback onRefresh;
  final ValueChanged<String> onAnalyzeMarket;
  final ValueChanged<MarketAlternative>? onAddToSlip;

  const MarketAlternativesPanel({
    super.key,
    required this.isLoading,
    required this.error,
    required this.markets,
    required this.onRefresh,
    required this.onAnalyzeMarket,
    this.onAddToSlip,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 0,
      color: Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(24),
        side: BorderSide(
          color: Colors.black.withOpacity(0.06),
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _Header(
              isLoading: isLoading,
              onRefresh: onRefresh,
            ),
            const SizedBox(height: 10),
            if (isLoading) const LinearProgressIndicator(),
            if (error != null) ...[
              const SizedBox(height: 10),
              _ErrorBox(
                message: error!,
                onRetry: onRefresh,
              ),
            ],
            if (!isLoading && error == null && markets.isEmpty)
              const _EmptyState(),
            if (!isLoading && markets.isNotEmpty) ...[
              const SizedBox(height: 8),
              ...markets.map(
                (market) => _MarketAlternativeCard(
                  item: market,
                  onAnalyzeMarket: onAnalyzeMarket,
                  onAddToSlip: onAddToSlip,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  final bool isLoading;
  final VoidCallback onRefresh;

  const _Header({
    required this.isLoading,
    required this.onRefresh,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        const Icon(
          Icons.account_tree_outlined,
          color: Color(0xFF2563EB),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            'Market Alternatives Explorer',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w900,
                ),
          ),
        ),
        IconButton(
          tooltip: 'Refresh alternatives',
          onPressed: isLoading ? null : onRefresh,
          icon: const Icon(Icons.refresh),
        ),
      ],
    );
  }
}

class _MarketAlternativeCard extends StatelessWidget {
  final MarketAlternative item;
  final ValueChanged<String> onAnalyzeMarket;
  final ValueChanged<MarketAlternative>? onAddToSlip;

  const _MarketAlternativeCard({
    required this.item,
    required this.onAnalyzeMarket,
    required this.onAddToSlip,
  });

  @override
  Widget build(BuildContext context) {
    final confidence = item.confidence == null
        ? '—'
        : '${(item.confidence! * 100).toStringAsFixed(1)}%';

    final odds = item.odds == null ? '—' : item.odds!.toStringAsFixed(2);
    final executionScore = _scoreText(item.executionScore);
    final survivability = _scoreText(item.survivabilityScore);
    final localRealism = _scoreText(item.localRealismScore);

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: item.executionReady ? const Color(0xFFF8FAFC) : const Color(0xFFFFFBEB),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: item.executionReady
              ? const Color(0xFF2563EB).withOpacity(0.12)
              : const Color(0xFF92400E).withOpacity(0.18),
        ),
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
                color: item.executionReady
                    ? const Color(0xFF166534)
                    : const Color(0xFF92400E),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  _marketLabel(item.market),
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w900,
                      ),
                ),
              ),
              Text(
                confidence,
                style: const TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w900,
                  color: Color(0xFF0F172A),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            _marketLabel(item.predictedLabel),
            style: const TextStyle(
              color: Colors.black54,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(child: _Metric(label: 'Confidence', value: confidence)),
              Expanded(child: _Metric(label: 'Odds', value: odds)),
              Expanded(child: _Metric(label: 'Kenya', value: item.kenyaGrade)),
            ],
          ),
          const SizedBox(height: 12),
          _InfoRow(label: 'Execution market', value: item.executionMarket),
          _InfoRow(label: 'Execution selection', value: item.executionSelection),
          _InfoRow(label: 'Bookmaker', value: item.bookmaker),
          _InfoRow(label: 'Bookmaker locality', value: item.bookmakerLocality),
          _InfoRow(label: 'Execution score', value: executionScore),
          _InfoRow(label: 'Survivability', value: survivability),
          _InfoRow(label: 'Local realism', value: localRealism),
          if (!item.isKenyaSuitable) ...[
            const SizedBox(height: 8),
            const _WarningText(
              text:
                  'Weak Kenyan suitability. Check local bookmaker availability before using this pick.',
            ),
          ],
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () => onAnalyzeMarket(item.market),
                  icon: const Icon(Icons.analytics_outlined),
                  label: const Text('Analyze'),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: FilledButton.icon(
                  onPressed: onAddToSlip == null ? null : () => onAddToSlip!(item),
                  icon: const Icon(Icons.playlist_add),
                  label: const Text('Add To Slip'),
                ),
              ),
            ],
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
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          value == '—' ? 'Unknown' : value,
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
    if (value == '—' || value.trim().isEmpty) {
      return const SizedBox.shrink();
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
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

class _WarningText extends StatelessWidget {
  final String text;

  const _WarningText({
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
      child: Row(
        children: [
          const Icon(
            Icons.info_outline,
            color: Color(0xFF92400E),
            size: 18,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(
                color: Color(0xFF92400E),
                fontWeight: FontWeight.w800,
                fontSize: 12,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _Pill extends StatelessWidget {
  final String text;
  final Color background;
  final Color foreground;

  const _Pill({
    required this.text,
    required this.background,
    required this.foreground,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: 10,
        vertical: 6,
      ),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        text,
        style: TextStyle(
          color: foreground,
          fontWeight: FontWeight.w900,
          fontSize: 12,
        ),
      ),
    );
  }
}

class _ErrorBox extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;

  const _ErrorBox({
    required this.message,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(13),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF1F2),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: const Color(0xFF9F1239).withOpacity(0.2),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Could not load market alternatives',
            style: TextStyle(
              color: Color(0xFF9F1239),
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            message,
            style: const TextStyle(
              color: Color(0xFF9F1239),
              fontSize: 12,
            ),
          ),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh),
            label: const Text('Retry'),
          ),
        ],
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(16),
      ),
      child: const Text(
        'No market alternatives available yet.',
        style: TextStyle(
          color: Colors.black54,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
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