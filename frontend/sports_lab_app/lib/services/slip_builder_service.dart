// lib/services/slip_builder_service.dart

import 'package:flutter/foundation.dart';

import '../models/slip_pick.dart';

class SlipBuilderService extends ChangeNotifier {
  static final SlipBuilderService instance = SlipBuilderService._internal();

  SlipBuilderService._internal();

  final List<SlipPick> _items = [];

  List<SlipPick> get items => List.unmodifiable(_items);

  bool get isEmpty => _items.isEmpty;

  int get count => _items.length;

  void add(SlipPick pick) {
    final exists = _items.any(
      (item) =>
          item.matchId == pick.matchId &&
          item.market == pick.market &&
          item.selection == pick.selection,
    );

    if (exists) return;

    _items.add(pick);
    notifyListeners();
  }

  void removeAt(int index) {
    if (index < 0 || index >= _items.length) return;

    _items.removeAt(index);
    notifyListeners();
  }

  void clear() {
    _items.clear();
    notifyListeners();
  }

  double get totalOdds {
    if (_items.isEmpty) return 0;

    return _items.fold<double>(
      1.0,
      (value, item) => value * item.effectiveOdds,
    );
  }

  double? get averageConfidence {
    final values = _items
        .map((item) => item.confidence)
        .whereType<double>()
        .toList();

    if (values.isEmpty) return null;

    return values.reduce((a, b) => a + b) / values.length;
  }

  double? get averageExecutionScore {
    final values = _items
        .map((item) => item.executionScore)
        .whereType<double>()
        .toList();

    if (values.isEmpty) return null;

    return values.reduce((a, b) => a + b) / values.length;
  }

  double? get averageSurvivability {
    final values = _items
        .map((item) => item.survivabilityScore)
        .whereType<double>()
        .toList();

    if (values.isEmpty) return null;

    return values.reduce((a, b) => a + b) / values.length;
  }

  String get riskLevel {
    final confidence = averageConfidence ?? 0;
    final execution = averageExecutionScore ?? 0;
    final survivability = averageSurvivability ?? 0;

    if (_items.length >= 8) return 'High Risk';
    if (confidence >= 0.70 && execution >= 70 && survivability >= 0.55) {
      return 'Safer';
    }
    if (confidence >= 0.60) return 'Medium Risk';

    return 'High Risk';
  }
}