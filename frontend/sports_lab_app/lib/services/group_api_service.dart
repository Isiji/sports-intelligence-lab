// lib/services/group_api_service.dart

import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import '../models/group_dashboard_item.dart';

class GroupSlate {
  final String slate;
  final int groupCount;
  final int pickCount;

  const GroupSlate({
    required this.slate,
    required this.groupCount,
    required this.pickCount,
  });

  factory GroupSlate.fromJson(Map<String, dynamic> json) {
    return GroupSlate(
      slate: json['slate']?.toString() ?? '',
      groupCount: _intValue(json['group_count']),
      pickCount: _intValue(json['pick_count']),
    );
  }
}

class GroupApiService {
  const GroupApiService();

  static const Duration _timeout = Duration(seconds: 90);

  Future<List<GroupSlate>> listGroupSlates({
    int limit = 50,
  }) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/groups/slates').replace(
      queryParameters: {
        'limit': limit.clamp(1, 200).toString(),
      },
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
        throw Exception('Invalid group slates response.');
      }

      return decoded
          .whereType<Map<String, dynamic>>()
          .map(GroupSlate.fromJson)
          .where((x) => x.slate.trim().isNotEmpty)
          .toList();
    } on TimeoutException catch (e) {
      throw Exception('Group slates timeout\nURL: $uri\nError: $e');
    } catch (e, stackTrace) {
      _logError(uri, e, stackTrace);
      throw Exception('Group API error\nURL: $uri\nError: $e');
    }
  }

  Future<List<GroupDashboardItem>> listGroups({
    required String slate,
    int limit = 500,
  }) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/groups').replace(
      queryParameters: {
        'slate': slate.trim(),
        'limit': limit.clamp(1, 1000).toString(),
      },
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
      throw Exception('Group API timeout\nURL: $uri\nError: $e');
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

int _intValue(dynamic value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  if (value is String) return int.tryParse(value) ?? 0;
  return 0;
}