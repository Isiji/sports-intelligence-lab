// lib/services/prediction_api_service.dart

import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/match_intelligence.dart';
import '../models/match_summary.dart';

class PredictionApiService {
  const PredictionApiService();

  static const Duration _timeout = Duration(seconds: 90);

  String _formatDateTime(DateTime value) {
    final y = value.year.toString().padLeft(4, '0');
    final m = value.month.toString().padLeft(2, '0');
    final d = value.day.toString().padLeft(2, '0');
    final h = value.hour.toString().padLeft(2, '0');
    final min = value.minute.toString().padLeft(2, '0');
    final s = value.second.toString().padLeft(2, '0');

    return '$y-$m-${d}T$h:$min:$s';
  }

  Future<List<MatchSummary>> searchMatches({
    String? team,
    String? league,
    DateTime? dateFrom,
    DateTime? dateTo,
    int limit = 100,
  }) async {
    final safeLimit = limit.clamp(1, 100);

    final query = <String, String>{
      'limit': safeLimit.toString(),
    };

    if (team != null && team.trim().isNotEmpty) {
      query['team'] = team.trim();
    }

    if (league != null && league.trim().isNotEmpty) {
      query['league'] = league.trim();
    }

    if (dateFrom != null) {
      query['date_from'] = _formatDateTime(dateFrom);
    }

    if (dateTo != null) {
      query['date_to'] = _formatDateTime(dateTo);
    }

    final uri = Uri.parse(
      '${ApiConfig.baseUrl}/predictions/search-matches',
    ).replace(
      queryParameters: query,
    );

    return _getMatchSummaries(uri);
  }

  Future<MatchIntelligence> getMatchIntelligence(int matchId) async {
    final uri = Uri.parse(
      '${ApiConfig.baseUrl}/predictions/match/$matchId',
    );

    return _getMatchIntelligence(uri);
  }

  Future<MatchIntelligence> analyzeMatch({
    required int matchId,
    required String market,
  }) async {
    final uri = Uri.parse(
      '${ApiConfig.baseUrl}/predictions/match/$matchId/analyze',
    ).replace(
      queryParameters: {
        'market': market,
      },
    );

    return _postMatchIntelligence(uri);
  }

  Future<MatchIntelligence> analyzeMatch1x2({
    required int matchId,
  }) async {
    final uri = Uri.parse(
      '${ApiConfig.baseUrl}/predictions/match/$matchId/analyze-1x2',
    );

    return _postMatchIntelligence(uri);
  }

  Future<MatchIntelligence> analyzeMatch1X2(int matchId) async {
    return analyzeMatch1x2(matchId: matchId);
  }

  Future<MarketAlternativesResponse> getMarketAlternatives({
    required int matchId,
  }) async {
    final uri = Uri.parse(
      '${ApiConfig.baseUrl}/predictions/match/$matchId/market-alternatives',
    );

    try {
      _logRequest('POST', uri);

      final response = await http.post(uri).timeout(_timeout);

      _logResponse(uri, response);

      if (response.statusCode != 200 && response.statusCode != 201) {
        throw Exception(_failureMessage(uri, response));
      }

      final decoded = jsonDecode(response.body);

      if (decoded is! Map<String, dynamic>) {
        throw Exception(
          'Invalid market alternatives response: ${response.body}',
        );
      }

      return MarketAlternativesResponse.fromJson(decoded);
    } on TimeoutException catch (e) {
      debugPrint('API timeout: $uri $e');

      throw Exception(
        'API timeout\nURL: $uri\nError: $e',
      );
    } catch (e, stackTrace) {
      _logError(uri, e, stackTrace);

      throw Exception(
        'API error\nURL: $uri\nError: $e',
      );
    }
  }

  Future<MatchIntelligence> _getMatchIntelligence(Uri uri) async {
    try {
      _logRequest('GET', uri);

      final response = await http.get(uri).timeout(_timeout);

      _logResponse(uri, response);

      if (response.statusCode != 200) {
        throw Exception(_failureMessage(uri, response));
      }

      final decoded = jsonDecode(response.body);

      if (decoded is! Map<String, dynamic>) {
        throw Exception(
          'Invalid match intelligence response: ${response.body}',
        );
      }

      return MatchIntelligence.fromJson(decoded);
    } on TimeoutException catch (e) {
      debugPrint('API timeout: $uri $e');

      throw Exception(
        'API timeout\nURL: $uri\nError: $e',
      );
    } catch (e, stackTrace) {
      _logError(uri, e, stackTrace);

      throw Exception(
        'API error\nURL: $uri\nError: $e',
      );
    }
  }

  Future<MatchIntelligence> _postMatchIntelligence(Uri uri) async {
    try {
      _logRequest('POST', uri);

      final response = await http.post(uri).timeout(_timeout);

      _logResponse(uri, response);

      if (response.statusCode != 200 && response.statusCode != 201) {
        throw Exception(_failureMessage(uri, response));
      }

      final decoded = jsonDecode(response.body);

      if (decoded is! Map<String, dynamic>) {
        throw Exception(
          'Invalid analyze response: ${response.body}',
        );
      }

      return MatchIntelligence.fromJson(decoded);
    } on TimeoutException catch (e) {
      debugPrint('API timeout: $uri $e');

      throw Exception(
        'API timeout\nURL: $uri\nError: $e',
      );
    } catch (e, stackTrace) {
      _logError(uri, e, stackTrace);

      throw Exception(
        'API error\nURL: $uri\nError: $e',
      );
    }
  }

  Future<List<MatchSummary>> _getMatchSummaries(Uri uri) async {
    try {
      _logRequest('GET', uri);

      final response = await http.get(uri).timeout(_timeout);

      _logResponse(uri, response);

      if (response.statusCode != 200) {
        throw Exception(_failureMessage(uri, response));
      }

      final decoded = jsonDecode(response.body);

      final List<dynamic> items;

      if (decoded is List) {
        items = decoded;
      } else if (decoded is Map<String, dynamic>) {
        items = decoded['matches'] ??
            decoded['items'] ??
            decoded['data'] ??
            [];
      } else {
        items = [];
      }

      return items
          .whereType<Map<String, dynamic>>()
          .map(MatchSummary.fromJson)
          .toList();
    } on TimeoutException catch (e) {
      debugPrint('API timeout: $uri $e');

      throw Exception(
        'API timeout\nURL: $uri\nError: $e',
      );
    } catch (e, stackTrace) {
      _logError(uri, e, stackTrace);

      throw Exception(
        'API error\nURL: $uri\nError: $e',
      );
    }
  }

  String _failureMessage(
    Uri uri,
    http.Response response,
  ) {
    return 'API failed\n'
        'URL: $uri\n'
        'Status: ${response.statusCode}\n'
        'Body: ${response.body}';
  }

  void _logRequest(
    String method,
    Uri uri,
  ) {
    debugPrint('');
    debugPrint('================ API REQUEST ================');
    debugPrint('$method $uri');
  }

  void _logResponse(
    Uri uri,
    http.Response response,
  ) {
    debugPrint('================ API RESPONSE ===============');
    debugPrint('URL: $uri');
    debugPrint('STATUS: ${response.statusCode}');
    debugPrint('BODY: ${response.body}');
    debugPrint('============================================');
  }

  void _logError(
    Uri uri,
    Object e,
    StackTrace stackTrace,
  ) {
    debugPrint('');
    debugPrint('================ API ERROR ==================');
    debugPrint('URL: $uri');
    debugPrint('ERROR: $e');
    debugPrint('STACKTRACE: $stackTrace');
    debugPrint('============================================');
  }
}