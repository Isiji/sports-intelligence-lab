// lib/widgets/production_pick_card.dart

import 'package:flutter/material.dart';

class ProductionPickCard extends StatelessWidget {
  final Map<String, dynamic> pick;

  const ProductionPickCard({
    super.key,
    required this.pick,
  });

  @override
  Widget build(BuildContext context) {
    final home = '${pick['home_team'] ?? ''}';
    final away = '${pick['away_team'] ?? ''}';
    final league = '${pick['league'] ?? ''}';
    final market = '${pick['market'] ?? '-'}';
    final label = '${pick['predicted_label'] ?? '-'}';
    final verdict = '${pick['execution_market_verdict'] ?? 'UNKNOWN'}';
    final ready = pick['execution_ready'] == true;

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '$home vs $away',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const SizedBox(height: 4),
            Text(league),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                _chip('Market: $market'),
                _chip('Pick: $label'),
                _chip('Conf: ${_percent(pick['confidence'])}'),
                _chip('Odds: ${pick['odds'] ?? '-'}'),
                _chip('Exec: ${pick['execution_score'] ?? '-'}'),
                _chip('Bookmaker: ${pick['odds_bookmaker'] ?? '-'}'),
                _chip(verdict),
                _chip(ready ? 'READY' : 'NOT READY'),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _chip(String text) {
    return Chip(
      label: Text(text),
      visualDensity: VisualDensity.compact,
    );
  }

  String _percent(dynamic value) {
    final number = double.tryParse('$value') ?? 0;
    return '${(number * 100).toStringAsFixed(1)}%';
  }
}