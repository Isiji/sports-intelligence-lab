import 'package:flutter/material.dart';

import '../models/match_summary.dart';

class MatchCard extends StatelessWidget {
  final MatchSummary match;
  final VoidCallback onTap;

  const MatchCard({
    super.key,
    required this.match,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final title = '${match.homeTeam} vs ${match.awayTeam}';

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
              ),
              const SizedBox(height: 6),
              Text(
                '${match.league} ${match.season}',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              const SizedBox(height: 6),
              Text(
                'Kickoff EAT: ${match.kickoffEat ?? 'Unknown'}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
              const SizedBox(height: 10),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  _Chip(
                    label: match.hasOdds ? 'Odds available' : 'No odds',
                    isGood: match.hasOdds,
                  ),
                  _Chip(
                    label: match.hasPrediction
                        ? '${match.predictionCount} prediction(s)'
                        : 'Not predicted',
                    isGood: match.hasPrediction,
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  final String label;
  final bool isGood;

  const _Chip({
    required this.label,
    required this.isGood,
  });

  @override
  Widget build(BuildContext context) {
    return Chip(
      label: Text(label),
      avatar: Icon(
        isGood ? Icons.check_circle : Icons.warning_amber_rounded,
        size: 18,
      ),
    );
  }
}