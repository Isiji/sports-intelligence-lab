// lib/services/automation_api_service.dart

import 'dart:convert';
import '../config/api_config.dart';
import 'package:http/http.dart' as http;

class AutomationJobItem {
  final int id;
  final String jobKey;
  final bool enabled;
  final String cronExpression;
  final String? nextRunAt;
  final String? lastRunAt;
  final String lastStatus;
  final String? createdAt;

  const AutomationJobItem({
    required this.id,
    required this.jobKey,
    required this.enabled,
    required this.cronExpression,
    required this.nextRunAt,
    required this.lastRunAt,
    required this.lastStatus,
    required this.createdAt,
  });

  factory AutomationJobItem.fromJson(Map<String, dynamic> json) {
    return AutomationJobItem(
      id: int.tryParse((json['id'] ?? '0').toString()) ?? 0,
      jobKey: (json['job_key'] ?? '').toString(),
      enabled: json['enabled'] == true,
      cronExpression: (json['cron_expression'] ?? '').toString(),
      nextRunAt: json['next_run_at']?.toString(),
      lastRunAt: json['last_run_at']?.toString(),
      lastStatus: (json['last_status'] ?? 'never_run').toString(),
      createdAt: json['created_at']?.toString(),
    );
  }

  String get title {
    return jobKey
        .replaceAll('_', ' ')
        .split(' ')
        .map((word) => word.isEmpty ? word : '${word[0].toUpperCase()}${word.substring(1)}')
        .join(' ');
  }
}

class AutomationCommandLogItem {
  final int index;
  final String command;
  final String status;
  final String? startedAt;
  final String? finishedAt;
  final double? durationSeconds;
  final String stdout;
  final String stderr;

  const AutomationCommandLogItem({
    required this.index,
    required this.command,
    required this.status,
    required this.startedAt,
    required this.finishedAt,
    required this.durationSeconds,
    required this.stdout,
    required this.stderr,
  });

  factory AutomationCommandLogItem.fromJson(Map<String, dynamic> json) {
    return AutomationCommandLogItem(
      index: int.tryParse((json['index'] ?? '0').toString()) ?? 0,
      command: (json['command'] ?? '').toString(),
      status: (json['status'] ?? '').toString(),
      startedAt: json['started_at']?.toString(),
      finishedAt: json['finished_at']?.toString(),
      durationSeconds: double.tryParse((json['duration_seconds'] ?? '').toString()),
      stdout: (json['stdout'] ?? '').toString(),
      stderr: (json['stderr'] ?? '').toString(),
    );
  }
}

class AutomationRunItem {
  final int id;
  final String jobKey;
  final String? startedAt;
  final String? finishedAt;
  final String status;
  final double? durationSeconds;
  final int? commandCount;
  final double progressPercent;
  final String? currentStep;
  final List<AutomationCommandLogItem> commandLog;
  final String? output;
  final String? error;

  const AutomationRunItem({
    required this.id,
    required this.jobKey,
    required this.startedAt,
    required this.finishedAt,
    required this.status,
    required this.durationSeconds,
    required this.commandCount,
    required this.progressPercent,
    required this.currentStep,
    required this.commandLog,
    required this.output,
    required this.error,
  });

  factory AutomationRunItem.fromJson(Map<String, dynamic> json) {
    final logs = (json['command_log'] as List?) ?? [];

    return AutomationRunItem(
      id: int.tryParse((json['id'] ?? '0').toString()) ?? 0,
      jobKey: (json['job_key'] ?? '').toString(),
      startedAt: json['started_at']?.toString(),
      finishedAt: json['finished_at']?.toString(),
      status: (json['status'] ?? '').toString(),
      durationSeconds: double.tryParse((json['duration_seconds'] ?? '').toString()),
      commandCount: int.tryParse((json['command_count'] ?? '').toString()),
      progressPercent: double.tryParse((json['progress_percent'] ?? '0').toString()) ?? 0,
      currentStep: json['current_step']?.toString(),
      commandLog: logs
          .map((item) => AutomationCommandLogItem.fromJson(item as Map<String, dynamic>))
          .toList(),
      output: json['output']?.toString(),
      error: json['error']?.toString(),
    );
  }

  String get title {
    return jobKey.replaceAll('_', ' ');
  }
}

class AutomationApiService {
  static const String baseUrl = ApiConfig.baseUrl;
  Future<void> seedJobs() async {
    final response = await http.post(Uri.parse('$baseUrl/automation/seed'));

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception('Failed to seed automation jobs: ${response.body}');
    }
  }

  Future<List<AutomationJobItem>> fetchJobs() async {
    final response = await http.get(Uri.parse('$baseUrl/automation/jobs'));
    final decoded = jsonDecode(response.body) as Map<String, dynamic>;

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception('Failed to load automation jobs: ${response.body}');
    }

    final items = (decoded['jobs'] as List?) ?? [];

    return items.map((item) => AutomationJobItem.fromJson(item as Map<String, dynamic>)).toList();
  }

  Future<List<AutomationRunItem>> fetchHistory({int limit = 50}) async {
    final response = await http.get(Uri.parse('$baseUrl/automation/history?limit=$limit'));
    final decoded = jsonDecode(response.body) as Map<String, dynamic>;

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception('Failed to load automation history: ${response.body}');
    }

    final items = (decoded['runs'] as List?) ?? [];

    return items.map((item) => AutomationRunItem.fromJson(item as Map<String, dynamic>)).toList();
  }

  Future<Map<String, dynamic>> runJob(String jobKey) async {
    final response = await http
        .post(
          Uri.parse('$baseUrl/automation/jobs/run'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'job_key': jobKey}),
        )
        .timeout(const Duration(minutes: 180));

    final decoded = jsonDecode(response.body) as Map<String, dynamic>;

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception('Job failed: ${response.body}');
    }

    return decoded;
  }

  Future<void> setEnabled({
    required String jobKey,
    required bool enabled,
  }) async {
    final path = enabled ? 'enable' : 'disable';

    final response = await http.post(
      Uri.parse('$baseUrl/automation/jobs/$path'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'job_key': jobKey}),
    );

    final decoded = jsonDecode(response.body) as Map<String, dynamic>;

    if (response.statusCode < 200 || response.statusCode >= 300 || decoded['ok'] != true) {
      throw Exception(decoded['error'] ?? 'Failed to update job');
    }
  }
}