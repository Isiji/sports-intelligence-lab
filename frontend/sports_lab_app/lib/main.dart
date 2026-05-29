// lib/main.dart

import 'package:flutter/material.dart';

import 'screens/production_review_dashboard_screen.dart';
import 'screens/groups_dashboard_screen.dart';
import 'screens/home_dashboard_screen.dart';
import 'screens/jackpot_builder_screen.dart';
import 'screens/placeholder_feature_screen.dart';
import 'screens/prediction_explorer_screen.dart';
import 'screens/predictions_dashboard_screen.dart';
import 'screens/slip_builder_screen.dart';

void main() {
  runApp(const SportsLabApp());
}

class SportsLabApp extends StatelessWidget {
  const SportsLabApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Sports Intelligence Lab',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorSchemeSeed: Colors.blue,
        useMaterial3: true,
      ),
      initialRoute: '/',
      routes: {
        '/': (_) => const HomeDashboardScreen(),
        '/prediction-explorer': (_) => const PredictionExplorerScreen(),
        '/match-intelligence': (_) => const PredictionExplorerScreen(),
        '/slip-builder': (_) => const SlipBuilderScreen(),
        '/jackpot-builder': (_) => const JackpotBuilderScreen(),
        '/market-alternatives': (_) => const PredictionExplorerScreen(),
        '/predictions-dashboard': (_) => const PredictionsDashboardScreen(),
        '/groups-dashboard': (_) => const GroupsDashboardScreen(),
        '/group-details': (_) => const GroupsDashboardScreen(),
        '/execution-ready-picks': (_) => const PredictionsDashboardScreen(
              initialExecutionReadyOnly: true,
            ),
        '/local-kenyan-picks': (_) => const PredictionsDashboardScreen(
              initialKenyanOnly: true,
            ),
        '/production-review': (_) => const ProductionReviewDashboardScreen(),        '/backtests': (_) => const PlaceholderFeatureScreen(
              title: 'Backtests',
              subtitle: 'Historical performance and ROI.',
              icon: Icons.history_outlined,
            ),
        '/intelligence-reports': (_) => const PlaceholderFeatureScreen(
              title: 'Intelligence Reports',
              subtitle: 'Market, league and odds intelligence.',
              icon: Icons.psychology_outlined,
            ),
        '/league-odds-coverage': (_) => const PlaceholderFeatureScreen(
              title: 'League / Odds Coverage',
              subtitle: 'Coverage and bookmaker depth.',
              icon: Icons.analytics_outlined,
            ),
        '/command-center': (_) => const PlaceholderFeatureScreen(
              title: 'Command Center / Admin Runner',
              subtitle: 'Run backend CLI workflows.',
              icon: Icons.terminal_outlined,
            ),
        '/data-ingestion': (_) => const PlaceholderFeatureScreen(
              title: 'Data Ingestion',
              subtitle: 'Fixtures, odds and stats ingestion.',
              icon: Icons.cloud_download_outlined,
            ),
        '/model-training': (_) => const PlaceholderFeatureScreen(
              title: 'Model Training',
              subtitle: 'Train models and rebuild intelligence.',
              icon: Icons.model_training_outlined,
            ),
        '/odds-stats-updates': (_) => const PlaceholderFeatureScreen(
              title: 'Odds / Stats Updates',
              subtitle: 'Refresh odds, stats and results.',
              icon: Icons.update_outlined,
            ),
        '/saved-slips-analysis': (_) => const PlaceholderFeatureScreen(
              title: 'Saved Slips / Saved Analysis',
              subtitle: 'Saved slips and analysis.',
              icon: Icons.bookmark_border_outlined,
            ),
        '/settings': (_) => const PlaceholderFeatureScreen(
              title: 'Settings',
              subtitle: 'App settings and preferences.',
              icon: Icons.settings_outlined,
            ),
      },
    );
  }
}