import 'package:flutter/material.dart';

import 'screens/prediction_explorer_screen.dart';

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
      home: const PredictionExplorerScreen(),
    );
  }
}