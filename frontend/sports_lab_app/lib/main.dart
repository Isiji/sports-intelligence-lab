// lib/main.dart

import 'package:flutter/material.dart';

import 'screens/home_dashboard_screen.dart';
import 'screens/jackpot_builder_screen.dart';
import 'screens/placeholder_feature_screen.dart';
import 'screens/prediction_explorer_screen.dart';
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

        // Match Intelligence needs a matchId, so this opens the selector first.
        '/match-intelligence': (_) => const PredictionExplorerScreen(),

        '/slip-builder': (_) => const SlipBuilderScreen(),

        '/jackpot-builder': (_) => const JackpotBuilderScreen(),

        '/market-alternatives': (_) => const PredictionExplorerScreen(),

        '/predictions-dashboard': (_) => const PlaceholderFeatureScreen(
              title: 'Predictions Dashboard',
              subtitle: 'Next screen: all predictions by date, slate, league and market.',
              icon: Icons.dashboard_customize_outlined,
            ),

        '/groups-dashboard': (_) => const PlaceholderFeatureScreen(
              title: 'Groups Dashboard',
              subtitle: 'Next screen: generated groups, group quality and grouped picks.',
              icon: Icons.groups_outlined,
            ),

        '/group-details': (_) => const PlaceholderFeatureScreen(
              title: 'Group Details',
              subtitle: 'Next screen: inspect one group with picks, risk and odds.',
              icon: Icons.account_tree_outlined,
            ),

        '/execution-ready-picks': (_) => const PlaceholderFeatureScreen(
              title: 'Execution-Ready Picks',
              subtitle: 'Picks passing execution checks.',
              icon: Icons.verified_outlined,
            ),

        '/local-kenyan-picks': (_) => const PlaceholderFeatureScreen(
              title: 'Local / Kenyan Picks',
              subtitle: 'Kenyan bookmaker-ready picks.',
              icon: Icons.location_on_outlined,
            ),

        '/production-review': (_) => const PlaceholderFeatureScreen(
              title: 'Production Review',
              subtitle: 'Review slate quality.',
              icon: Icons.fact_check_outlined,
            ),

        '/backtests': (_) => const PlaceholderFeatureScreen(
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
              subtitle: 'Run backend workflows.',
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