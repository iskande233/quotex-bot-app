import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:web_socket_channel/web_socket_channel.dart';

class ApiService {
  // Android emulator: 10.0.2.2. Physical phone: replace with your PC/server IP.
  static const String baseUrl = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://10.0.2.2:8000');
  static const String wsUrl = String.fromEnvironment('API_WS_URL', defaultValue: 'ws://10.0.2.2:8000/ws');

  static WebSocketChannel connectWs() => WebSocketChannel.connect(Uri.parse(wsUrl));

  static Future<Map<String, dynamic>> startBot({
    required String symbol,
    required double amount,
    required int maxTrades,
    String timeframe = 'M1',
  }) async {
    final res = await http.post(
      Uri.parse('$baseUrl/api/v1/bot/start'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'symbol': symbol,
        'timeframe': timeframe,
        'investment_amount': amount,
        'max_trades': maxTrades,
        'enabled': true,
      }),
    );
    return _decode(res);
  }

  static Future<Map<String, dynamic>> stopBot() async {
    final res = await http.post(Uri.parse('$baseUrl/api/v1/bot/stop'));
    return _decode(res);
  }

  static Future<Map<String, dynamic>> status() async {
    final res = await http.get(Uri.parse('$baseUrl/api/v1/bot/status'));
    return _decode(res);
  }


  static Future<Map<String, dynamic>> login({
    required String email,
    required String password,
    required String accountType,
  }) async {
    final res = await http.post(
      Uri.parse('$baseUrl/api/v1/auth/login'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'email': email, 'password': password, 'account_type': accountType}),
    );
    return _decode(res);
  }

  static Future<Map<String, dynamic>> logout() async {
    final res = await http.post(Uri.parse('$baseUrl/api/v1/auth/logout'));
    return _decode(res);
  }

  static Future<Map<String, dynamic>> session() async {
    final res = await http.get(Uri.parse('$baseUrl/api/v1/auth/session'));
    return _decode(res);
  }

  static Future<Map<String, dynamic>> switchMode(String mode) async {
    final res = await http.post(Uri.parse('$baseUrl/api/v1/mode/$mode'));
    return _decode(res);
  }

  static Map<String, dynamic> _decode(http.Response res) {
    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw Exception('HTTP ${res.statusCode}: ${res.body}');
    }
    return jsonDecode(res.body) as Map<String, dynamic>;
  }
}
