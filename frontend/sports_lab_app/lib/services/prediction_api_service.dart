// lib/services/prediction_api_service.dart

import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/match_summary.dart';

class PredictionApiService {
  const PredictionApiService();

  static const Duration _timeout = Duration(seconds: 20);

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

    final uri = Uri.parse('${ApiConfig.baseUrl}/predictions/search-matches')
        .replace(queryParameters: query);

    return _getMatchSummaries(uri);
  }

  Future<List<MatchSummary>> _getMatchSummaries(Uri uri) async {
    try {
      debugPrint('');
      debugPrint('================ API REQUEST ================');
      debugPrint('GET $uri');

      final response = await http.get(uri).timeout(_timeout);

      debugPrint('================ API RESPONSE ===============');
      debugPrint('URL: $uri');
      debugPrint('STATUS: ${response.statusCode}');
      debugPrint('BODY: ${response.body}');
      debugPrint('============================================');

      if (response.statusCode != 200) {
        throw Exception(
          'API failed\n'
          'URL: $uri\n'
          'Status: ${response.statusCode}\n'
          'Body: ${response.body}',
        );
      }

      final decoded = jsonDecode(response.body);

      final List<dynamic> items;

      if (decoded is List) {
        items = decoded;
      } else if (decoded is Map<String, dynamic>) {
        items = decoded['matches'] ?? decoded['items'] ?? decoded['data'] ?? [];
      } else {
        items = [];
      }

      return items
          .whereType<Map<String, dynamic>>()
          .map(MatchSummary.fromJson)
          .toList();
    } on TimeoutException catch (e) {
      debugPrint('');
      debugPrint('================ API TIMEOUT ================');
      debugPrint('URL: $uri');
      debugPrint('ERROR: $e');
      debugPrint('============================================');

      throw Exception(
        'API timeout\n'
        'URL: $uri\n'
        'Error: $e',
      );
    } catch (e, stackTrace) {
      debugPrint('');
      debugPrint('================ API ERROR ==================');
      debugPrint('URL: $uri');
      debugPrint('ERROR: $e');
      debugPrint('STACKTRACE: $stackTrace');
      debugPrint('============================================');

      throw Exception(
        'API error\n'
        'URL: $uri\n'
        'Error: $e',
      );
    }
  }
}