// lib/widgets/production_health_cards.dart

import 'package:flutter/material.dart';

class ProductionHealthCards extends StatelessWidget {
  final Map<String, dynamic> summary;
  final Map<String, dynamic> health;

  const ProductionHealthCards({
    super.key,
    required this.summary,
    required this.health,
  });

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 12,
      runSpacing: 12,
      children: [
        _card(
          context,
          'Total Predictions',
          summary['total_predictions'],
          Icons.analytics_outlined,
        ),
        _card(
          context,
          'With Odds',
          summary['predictions_with_odds'],
          Icons.percent_outlined,
        ),
        _card(
          context,
          'Execution Ready',
          health['execution_ready_picks'],
          Icons.verified_outlined,
        ),
        _card(
          context,
          'Local Picks',
          health['local_bookmaker_picks'],
          Icons.location_on_outlined,
        ),
        _card(
          context,
          'Stale Odds',
          health['stale_odds_picks'],
          Icons.warning_amber_outlined,
        ),
        _card(
          context,
          'Blocked',
          health['blocked_picks'],
          Icons.block_outlined,
        ),
      ],
    );
  }

  Widget _card(
    BuildContext context,
    String title,
    dynamic value,
    IconData icon,
  ) {
    return SizedBox(
      width: 180,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon),
              const SizedBox(height: 10),
              Text(
                title,
                style: Theme.of(context).textTheme.labelMedium,
              ),
              const SizedBox(height: 6),
              Text(
                '${value ?? 0}',
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}