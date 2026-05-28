// lib/models/match_intelligence.dart

class MatchIntelligence {
  final Map<String, dynamic> raw;

  MatchIntelligence({
    required this.raw,
  });

  factory MatchIntelligence.fromJson(Map<String, dynamic> json) {
    return MatchIntelligence(raw: json);
  }

  int? get matchId => _intValue([
        raw['match_id'],
        raw['id'],
        _match['match_id'],
        _match['id'],
      ]);

  String get league => _stringValue([
        raw['league'],
        _match['league'],
      ]);

  String get homeTeam => _stringValue([
        raw['home_team'],
        _match['home_team'],
      ]);

  String get awayTeam => _stringValue([
        raw['away_team'],
        _match['away_team'],
      ]);

  String get kickoff => _stringValue([
        raw['kickoff_eat'],
        raw['kickoff_datetime'],
        raw['kickoff_date'],
        _match['kickoff_eat'],
        _match['kickoff_datetime'],
        _match['kickoff_date'],
      ]);

  List<PredictionPick> get savedPredictions {
    final source = raw['predictions'] ??
        raw['saved_predictions'] ??
        raw['items'] ??
        raw['data'];

    if (source is List) {
      return source
          .whereType<Map<String, dynamic>>()
          .map(PredictionPick.fromJson)
          .toList();
    }

    return [];
  }

  PredictionPick? get analysis {
    final source = raw['analysis'] ??
        raw['prediction'] ??
        raw['result'] ??
        raw['latest_prediction'];

    if (source is Map<String, dynamic>) {
      return PredictionPick.fromJson(source);
    }

    if (savedPredictions.isNotEmpty) {
      return savedPredictions.first;
    }

    return null;
  }

  Map<String, dynamic> get _match {
    final value = raw['match'];
    if (value is Map<String, dynamic>) return value;
    return {};
  }

  static String _stringValue(List<dynamic> values) {
    for (final value in values) {
      if (value != null && value.toString().trim().isNotEmpty) {
        return value.toString();
      }
    }
    return '—';
  }

  static int? _intValue(List<dynamic> values) {
    for (final value in values) {
      if (value is int) return value;
      if (value is String) return int.tryParse(value);
    }
    return null;
  }
}

class PredictionPick {
  final Map<String, dynamic> raw;

  PredictionPick({
    required this.raw,
  });

  factory PredictionPick.fromJson(Map<String, dynamic> json) {
    return PredictionPick(raw: json);
  }

  String get market => _stringValue([
        raw['market'],
        raw['model_market'],
        raw['execution_market'],
      ]);

  String get label => _stringValue([
        raw['predicted_label'],
        raw['prediction'],
        raw['selection'],
        raw['execution_selection'],
      ]);

  String get executionMarket => _stringValue([
        raw['execution_market'],
        raw['market'],
      ]);

  String get executionSelection => _stringValue([
        raw['execution_selection'],
        raw['selection'],
        raw['predicted_label'],
      ]);

  String get bookmaker => _stringValue([
        raw['odds_bookmaker'],
        raw['bookmaker'],
        raw['provider'],
      ]);

  String get reasoning => _stringValue([
        raw['reasoning'],
        raw['explanation'],
        raw['reason'],
        raw['analysis_reason'],
      ]);

  String get timingRisk => _stringValue([
        raw['timing_risk'],
        raw['market_timing_risk'],
      ]);

  String get localRealism => _stringValue([
        raw['local_realism'],
        raw['local_realism_score'],
        raw['kenyan_realism_score'],
      ]);

  double? get confidence => _doubleValue([
        raw['confidence'],
        raw['probability'],
      ]);

  double? get odds => _doubleValue([
        raw['odds'],
        raw['best_odds'],
        raw['execution_odds'],
      ]);

  double? get valueScore => _doubleValue([
        raw['value_score'],
        raw['edge'],
      ]);

  static String _stringValue(List<dynamic> values) {
    for (final value in values) {
      if (value != null && value.toString().trim().isNotEmpty) {
        return value.toString();
      }
    }
    return '—';
  }

  static double? _doubleValue(List<dynamic> values) {
    for (final value in values) {
      if (value is num) return value.toDouble();
      if (value is String) return double.tryParse(value);
    }
    return null;
  }
}