// lib/services/group_api_service.dart

import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/group_dashboard_item.dart';

class GroupApiService {
  const GroupApiService();

  static const Duration _timeout = Duration(seconds: 180);

  Future<List<GroupDashboardItem>> listGroups({
    String? slate,
    int limit = 300,
  }) async {
    final query = <String, String>{
      'limit': limit.clamp(1, 1000).toString(),
    };

    if (slate != null && slate.trim().isNotEmpty) {
      query['slate'] = slate.trim();
    }

    final uri = Uri.parse('${ApiConfig.baseUrl}/groups').replace(
      queryParameters: query,
    );

    try {
      _logRequest('GET', uri);

      final response = await http.get(uri).timeout(_timeout);

      _logResponse(uri, response);

      if (response.statusCode != 200) {
        throw Exception(_failureMessage(uri, response));
      }

      final decoded = jsonDecode(response.body);

      if (decoded is! List) {
        throw Exception('Invalid groups response.');
      }

      return decoded
          .whereType<Map<String, dynamic>>()
          .map(GroupDashboardItem.fromJson)
          .toList();
    } on TimeoutException catch (e) {
      debugPrint('GROUP API TIMEOUT: $uri $e');
      throw Exception('Group API timeout\nURL: $uri\nError: $e');
    } catch (e, stackTrace) {
      _logError(uri, e, stackTrace);
      throw Exception('Group API error\nURL: $uri\nError: $e');
    }
  }

  Future<Map<String, dynamic>> createGroups({
    String? slate,
    double minConfidence = 0.65,
    double minGroupOdds = 3.0,
    bool requireOdds = false,
  }) async {
    final query = <String, String>{
      'min_confidence': minConfidence.toStringAsFixed(2),
      'min_group_odds': minGroupOdds.toStringAsFixed(2),
      'require_odds': requireOdds.toString(),
    };

    if (slate != null && slate.trim().isNotEmpty) {
      query['slate'] = slate.trim();
    }

    final uri = Uri.parse('${ApiConfig.baseUrl}/groups/create').replace(
      queryParameters: query,
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
        throw Exception('Invalid group create response.');
      }

      return decoded;
    } on TimeoutException catch (e) {
      debugPrint('GROUP CREATE TIMEOUT: $uri $e');
      throw Exception('Group create timeout\nURL: $uri\nError: $e');
    } catch (e, stackTrace) {
      _logError(uri, e, stackTrace);
      throw Exception('Group API error\nURL: $uri\nError: $e');
    }
  }

  String _failureMessage(Uri uri, http.Response response) {
    return 'API failed\n'
        'URL: $uri\n'
        'Status: ${response.statusCode}\n'
        'Body preview: ${_preview(response.body)}';
  }

  void _logRequest(String method, Uri uri) {
    debugPrint('');
    debugPrint('================ GROUP API REQUEST ================');
    debugPrint('$method $uri');
  }

  void _logResponse(Uri uri, http.Response response) {
    debugPrint('================ GROUP API RESPONSE ===============');
    debugPrint('URL: $uri');
    debugPrint('STATUS: ${response.statusCode}');
    debugPrint('BODY LENGTH: ${response.body.length}');
    debugPrint('BODY PREVIEW: ${_preview(response.body)}');
    debugPrint('==================================================');
  }

  void _logError(Uri uri, Object e, StackTrace stackTrace) {
    debugPrint('');
    debugPrint('================ GROUP API ERROR ==================');
    debugPrint('URL: $uri');
    debugPrint('ERROR: $e');
    debugPrint('STACKTRACE: $stackTrace');
    debugPrint('==================================================');
  }

  String _preview(String body) {
    if (body.length <= 700) return body;
    return '${body.substring(0, 700)}...';
  }
}