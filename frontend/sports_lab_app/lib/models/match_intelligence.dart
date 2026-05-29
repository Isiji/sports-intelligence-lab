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

  MarketAlternativesResponse? get marketAlternativesResponse {
    if (raw['markets'] is List) {
      return MarketAlternativesResponse.fromJson(raw);
    }

    final source = raw['market_alternatives'];

    if (source is Map<String, dynamic>) {
      return MarketAlternativesResponse.fromJson(source);
    }

    return null;
  }

  Map<String, dynamic> get _match {
    final value = raw['match'];

    if (value is Map<String, dynamic>) {
      return value;
    }

    return {};
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

  String get executionReady => _stringValue([
        raw['execution_ready'],
        raw['is_execution_ready'],
        raw['ready_for_execution'],
      ]);

  double? get executionScore => _doubleValue([
        raw['execution_score'],
        raw['bookmaker_execution_score'],
      ]);

  double? get survivabilityScore => _doubleValue([
        raw['survivability_score'],
        raw['market_survivability_score'],
      ]);

  String get bookmaker => _stringValue([
        raw['odds_bookmaker'],
        raw['bookmaker'],
        raw['provider'],
      ]);

  String get bookmakerLocality => _stringValue([
        raw['bookmaker_locality'],
        raw['locality'],
        raw['odds_locality'],
      ]);

  String get kenyanAvailability => _stringValue([
        raw['kenyan_availability'],
        raw['local_availability'],
        raw['bookmaker_availability'],
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

  double? get localRealismScore => _doubleValue([
        raw['local_realism_score'],
        raw['kenyan_realism_score'],
        raw['local_realism'],
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

  List<dynamic> get marketAlternatives {
    final value = raw['market_alternatives'] ?? raw['alternatives'];

    if (value is List) {
      return value;
    }

    if (value is Map && value['alternatives'] is List) {
      return value['alternatives'] as List;
    }

    return const [];
  }
}

class MarketAlternativesResponse {
  final Map<String, dynamic> raw;
  final List<MarketAlternative> markets;

  MarketAlternativesResponse({
    required this.raw,
    required this.markets,
  });

  factory MarketAlternativesResponse.fromJson(Map<String, dynamic> json) {
    final source = json['markets'];

    return MarketAlternativesResponse(
      raw: json,
      markets: source is List
          ? source
              .whereType<Map<String, dynamic>>()
              .map(MarketAlternative.fromJson)
              .toList()
          : [],
    );
  }

  int get count => markets.length;

  Map<String, dynamic> get match {
    final value = raw['match'];

    if (value is Map<String, dynamic>) {
      return value;
    }

    return {};
  }
}

class MarketAlternative {
  final Map<String, dynamic> raw;

  MarketAlternative({
    required this.raw,
  });

  factory MarketAlternative.fromJson(Map<String, dynamic> json) {
    return MarketAlternative(raw: json);
  }

  String get market => _stringValue([
        raw['market'],
      ]);

  String get predictedLabel => _stringValue([
        raw['predicted_label'],
        raw['selection'],
        raw['execution_selection'],
      ]);

  String get executionMarket => _stringValue([
        raw['execution_market'],
        raw['market'],
      ]);

  String get executionSelection => _stringValue([
        raw['execution_selection'],
        raw['predicted_label'],
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

  double? get executionScore => _doubleValue([
        raw['execution_score'],
      ]);

  bool get executionReady {
    final value = raw['execution_ready'];

    if (value is bool) return value;

    final text = value?.toString().toLowerCase().trim();

    return text == 'true' || text == '1' || text == 'yes' || text == 'ready';
  }

  double? get survivabilityScore => _doubleValue([
        raw['survivability_score'],
      ]);

  String get bookmaker => _stringValue([
        raw['bookmaker'],
        raw['odds_bookmaker'],
      ]);

  String get bookmakerLocality => _stringValue([
        raw['bookmaker_locality'],
      ]);

  double? get localRealismScore => _doubleValue([
        raw['local_realism_score'],
      ]);

  String get kenyaGrade {
    final score = localRealismScore;

    if (bookmakerLocality.toUpperCase() == 'LOCAL' && score != null && score >= 0.75) {
      return 'A';
    }

    if (score == null) return 'Unknown';
    if (score >= 0.75) return 'A';
    if (score >= 0.60) return 'B';
    if (score >= 0.45) return 'C';
    if (score >= 0.30) return 'D';

    return 'Weak';
  }

  bool get isKenyaSuitable {
    final score = localRealismScore ?? 0.0;

    return bookmakerLocality.toUpperCase() == 'LOCAL' || score >= 0.60;
  }
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

int? _intValue(List<dynamic> values) {
  for (final value in values) {
    if (value is int) return value;

    if (value is String) {
      return int.tryParse(value);
    }
  }

  return null;
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