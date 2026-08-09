import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'services/api_service.dart';

void main() => runApp(const QuotexBotApp());

class QuotexBotApp extends StatelessWidget {
  const QuotexBotApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Quotex Bot App',
      theme: ThemeData.dark(useMaterial3: true).copyWith(
        scaffoldBackgroundColor: const Color(0xFF050817),
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.amber, brightness: Brightness.dark),
      ),
      home: const BotHomePage(),
    );
  }
}

class BotHomePage extends StatefulWidget {
  const BotHomePage({super.key});
  @override
  State<BotHomePage> createState() => _BotHomePageState();
}

class _BotHomePageState extends State<BotHomePage> {
  final symbolCtrl = TextEditingController(text: 'EURUSD-OTC');
  final amountCtrl = TextEditingController(text: '1');
  final maxTradesCtrl = TextEditingController(text: '10');
  String timeframe = 'M1';
  String selectedMode = 'paper';
  WebSocketChannel? channel;
  StreamSubscription? sub;
  bool running = false;
  bool connecting = false;
  double balance = 0;
  double pnl = 0;
  double price = 0;
  String mode = 'PAPER';
  List<dynamic> history = [];
  List<dynamic> candles = [];
  String lastMessage = 'Waiting for backend...';
  final Set<String> notifiedResults = {};
  final Set<String> notifiedOpened = {};

  @override
  void initState() {
    super.initState();
    _connectWs();
  }

  @override
  void dispose() {
    sub?.cancel();
    channel?.sink.close();
    symbolCtrl.dispose();
    amountCtrl.dispose();
    maxTradesCtrl.dispose();
    super.dispose();
  }

  void _connectWs() {
    setState(() => connecting = true);
    try {
      sub?.cancel();
      channel?.sink.close();
      channel = ApiService.connectWs();
      sub = channel!.stream.listen((event) {
        final data = jsonDecode(event as String) as Map<String, dynamic>;
        final bal = data['balance'] as Map<String, dynamic>? ?? {};
        final status = data['status'] as Map<String, dynamic>? ?? {};
        final eventType = data['type']?.toString() ?? 'snapshot';
        final trade = data['trade'] as Map<String, dynamic>?;
        setState(() {
          balance = (bal['balance'] as num?)?.toDouble() ?? balance;
          pnl = (bal['session_pnl'] as num?)?.toDouble() ?? pnl;
          mode = bal['mode']?.toString() ?? mode;
          selectedMode = mode.toLowerCase();
          running = status['running'] == true;
          history = (data['history'] as List?) ?? history;
          candles = (data['candles'] as List?) ?? candles;
          price = (data['price'] as num?)?.toDouble() ?? price;
          lastMessage = 'Live: ${DateTime.now().toIso8601String().substring(11, 19)}';
          connecting = false;
        });
        if (trade != null) _handleTradeEvent(eventType, trade);
      }, onError: (_) {
        setState(() { connecting = false; lastMessage = 'WebSocket error. Check backend IP.'; });
      }, onDone: () {
        setState(() { connecting = false; lastMessage = 'WebSocket closed.'; });
      });
    } catch (e) {
      setState(() { connecting = false; lastMessage = 'WS failed: $e'; });
    }
  }

  void _handleTradeEvent(String eventType, Map<String, dynamic> trade) {
    final id = trade['id']?.toString() ?? '';
    if (id.isEmpty) return;
    if (eventType == 'trade_opened' && notifiedOpened.add(id)) {
      _showPopup('Trade Executed', '${trade['symbol']} ${trade['direction']} @ ${trade['entry_price']}', Colors.amber);
    }
    if (eventType == 'trade_result' && notifiedResults.add(id)) {
      final result = trade['result']?.toString() ?? 'PENDING';
      _showPopup('Trade Result: $result', '${trade['symbol']} PnL: ${trade['pnl']}', result == 'WIN' ? Colors.greenAccent : Colors.redAccent);
    }
  }

  void _showPopup(String title, String message, Color color) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      backgroundColor: const Color(0xFF111A35),
      content: Row(children: [
        Icon(Icons.notifications_active, color: color),
        const SizedBox(width: 10),
        Expanded(child: Text('$title\n$message')),
      ]),
      duration: const Duration(seconds: 4),
    ));
  }

  Future<void> _start() async {
    try {
      setState(() => lastMessage = 'Starting bot...');
      await ApiService.switchMode(selectedMode);
      await ApiService.startBot(
        symbol: symbolCtrl.text.trim(),
        amount: double.tryParse(amountCtrl.text) ?? 1,
        maxTrades: int.tryParse(maxTradesCtrl.text) ?? 10,
        timeframe: timeframe,
      );
      setState(() => lastMessage = 'Bot started');
    } catch (e) {
      setState(() => lastMessage = 'Start error: $e');
    }
  }

  Future<void> _stop() async {
    try {
      setState(() => lastMessage = 'Stopping bot...');
      await ApiService.stopBot();
      setState(() => lastMessage = 'Bot stopped');
    } catch (e) {
      setState(() => lastMessage = 'Stop error: $e');
    }
  }

  Future<void> _openLogin() async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => LoginPage(
      initialMode: selectedMode == 'real' ? 'real' : 'demo',
      onLoginSuccess: (m) {
        selectedMode = m.toLowerCase();
        mode = m.toUpperCase();
        setState(() {});
        _connectWs();
      },
    )));
  }

  Future<void> _openSettings() async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => SettingsPage(
      symbol: symbolCtrl.text,
      amount: amountCtrl.text,
      maxTrades: maxTradesCtrl.text,
      timeframe: timeframe,
      mode: selectedMode,
      onSave: (symbol, amount, maxTrades, tf, m) {
        symbolCtrl.text = symbol;
        amountCtrl.text = amount;
        maxTradesCtrl.text = maxTrades;
        timeframe = tf;
        selectedMode = m;
        setState(() {});
      },
    )));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Quotex Bot App'), actions: [
        IconButton(onPressed: _openLogin, icon: const Icon(Icons.login)),
        IconButton(onPressed: _openSettings, icon: const Icon(Icons.settings)),
        IconButton(onPressed: _connectWs, icon: const Icon(Icons.sync)),
      ]),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Row(children: [
            Expanded(child: ElevatedButton.icon(onPressed: running ? null : _start, icon: const Icon(Icons.play_arrow), label: const Text('START'))),
            const SizedBox(width: 12),
            Expanded(child: ElevatedButton.icon(onPressed: running ? _stop : null, icon: const Icon(Icons.stop), label: const Text('STOP'))),
          ]),
          const SizedBox(height: 12),
          _Panel(title: 'Configuration', child: Text('${symbolCtrl.text} | $timeframe | Amount: ${amountCtrl.text} | Max: ${maxTradesCtrl.text} | Mode: ${selectedMode.toUpperCase()}')),
          const SizedBox(height: 12),
          _Panel(title: 'Live Account', child: Text('Mode: $mode\nBalance: ${balance.toStringAsFixed(2)}\nSession PnL: ${pnl.toStringAsFixed(2)}\nBot: ${running ? 'RUNNING' : 'STOPPED'}\n$lastMessage')),
          const SizedBox(height: 12),
          _Panel(title: 'M1 Candlestick Chart', child: SizedBox(height: 230, child: _CandleChart(candles: candles, price: price))),
          const SizedBox(height: 12),
          _Panel(title: 'Trade History', child: _HistoryList(history: history)),
        ]),
      ),
    );
  }
}

class LoginPage extends StatefulWidget {
  final String initialMode;
  final void Function(String mode) onLoginSuccess;
  const LoginPage({super.key, required this.initialMode, required this.onLoginSuccess});
  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final emailCtrl = TextEditingController();
  final passCtrl = TextEditingController();
  late String accountType = widget.initialMode == 'real' ? 'real' : 'demo';
  bool loading = false;
  String message = '';

  @override
  void dispose() {
    emailCtrl.dispose();
    passCtrl.dispose();
    super.dispose();
  }

  Future<void> _login() async {
    setState(() { loading = true; message = 'Connecting to Quotex...'; });
    try {
      final res = await ApiService.login(email: emailCtrl.text.trim(), password: passCtrl.text, accountType: accountType);
      final m = res['mode']?.toString() ?? accountType.toUpperCase();
      widget.onLoginSuccess(m);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Logged in: $m')));
      Navigator.pop(context);
    } catch (e) {
      setState(() { message = 'Login failed: $e'; });
    } finally {
      if (mounted) setState(() { loading = false; });
    }
  }

  Future<void> _logout() async {
    setState(() { loading = true; message = 'Logging out...'; });
    try {
      await ApiService.logout();
      widget.onLoginSuccess('paper');
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Logged out to PAPER mode')));
      Navigator.pop(context);
    } catch (e) {
      setState(() { message = 'Logout failed: $e'; });
    } finally {
      if (mounted) setState(() { loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Quotex Login')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        const Text('Login creates an in-memory backend session. Use DEMO first. Credentials are not stored by the app.', style: TextStyle(color: Colors.amber)),
        const SizedBox(height: 16),
        TextField(controller: emailCtrl, keyboardType: TextInputType.emailAddress, decoration: const InputDecoration(labelText: 'Quotex Email')),
        TextField(controller: passCtrl, obscureText: true, decoration: const InputDecoration(labelText: 'Quotex Password')),
        const SizedBox(height: 16),
        DropdownButtonFormField<String>(value: accountType, items: const [
          DropdownMenuItem(value: 'demo', child: Text('Demo Account')),
          DropdownMenuItem(value: 'real', child: Text('Real Account')),
        ], onChanged: (v) => setState(() => accountType = v ?? 'demo'), decoration: const InputDecoration(labelText: 'Account Type')),
        const SizedBox(height: 22),
        ElevatedButton.icon(onPressed: loading ? null : _login, icon: const Icon(Icons.login), label: const Text('Login')),
        const SizedBox(height: 10),
        OutlinedButton.icon(onPressed: loading ? null : _logout, icon: const Icon(Icons.logout), label: const Text('Logout / Paper Mode')),
        if (message.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 16), child: Text(message)),
      ]),
    );
  }
}

class SettingsPage extends StatefulWidget {
  final String symbol, amount, maxTrades, timeframe, mode;
  final void Function(String symbol, String amount, String maxTrades, String timeframe, String mode) onSave;
  const SettingsPage({super.key, required this.symbol, required this.amount, required this.maxTrades, required this.timeframe, required this.mode, required this.onSave});
  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  late final TextEditingController symbolCtrl = TextEditingController(text: widget.symbol);
  late final TextEditingController amountCtrl = TextEditingController(text: widget.amount);
  late final TextEditingController maxTradesCtrl = TextEditingController(text: widget.maxTrades);
  late String timeframe = widget.timeframe;
  late String mode = widget.mode;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        TextField(controller: symbolCtrl, decoration: const InputDecoration(labelText: 'Symbol')),
        TextField(controller: amountCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Investment Amount')),
        TextField(controller: maxTradesCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Max Trades')),
        const SizedBox(height: 16),
        DropdownButtonFormField<String>(value: timeframe, items: const [DropdownMenuItem(value: 'M1', child: Text('M1'))], onChanged: (v) => setState(() => timeframe = v ?? 'M1'), decoration: const InputDecoration(labelText: 'Timeframe')),
        const SizedBox(height: 16),
        DropdownButtonFormField<String>(value: mode, items: const [
          DropdownMenuItem(value: 'paper', child: Text('Paper Mode')),
          DropdownMenuItem(value: 'demo', child: Text('Demo Account')),
          DropdownMenuItem(value: 'real', child: Text('Real Adapter Placeholder')),
        ], onChanged: (v) => setState(() => mode = v ?? 'paper'), decoration: const InputDecoration(labelText: 'Execution Mode')),
        const SizedBox(height: 22),
        ElevatedButton.icon(onPressed: () {
          widget.onSave(symbolCtrl.text, amountCtrl.text, maxTradesCtrl.text, timeframe, mode);
          Navigator.pop(context);
        }, icon: const Icon(Icons.save), label: const Text('Save Settings')),
        const SizedBox(height: 14),
        const Text('Safety: Paper/Demo are simulated. Real adapter requires a compliant user-owned Quotex session integration.', style: TextStyle(color: Colors.amber)),
      ]),
    );
  }
}

class _Panel extends StatelessWidget {
  final String title;
  final Widget child;
  const _Panel({required this.title, required this.child});
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: const Color(0xFF111A35), borderRadius: BorderRadius.circular(18), border: Border.all(color: Colors.amber.withOpacity(.5))),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(title, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.amber)),
        const SizedBox(height: 8),
        child,
      ]),
    );
  }
}

class _CandleChart extends StatelessWidget {
  final List<dynamic> candles;
  final double price;
  const _CandleChart({required this.candles, required this.price});
  @override
  Widget build(BuildContext context) => CustomPaint(painter: _CandlePainter(candles), child: Align(alignment: Alignment.topRight, child: Text('Live: ${price.toStringAsFixed(6)}')));
}

class _CandlePainter extends CustomPainter {
  final List<dynamic> candles;
  _CandlePainter(this.candles);
  @override
  void paint(Canvas canvas, Size size) {
    final grid = Paint()..color = Colors.white.withOpacity(.08)..strokeWidth = 1;
    for (var i = 1; i < 4; i++) canvas.drawLine(Offset(0, size.height * i / 4), Offset(size.width, size.height * i / 4), grid);
    if (candles.isEmpty) return;
    final list = candles.cast<Map>().toList();
    final highs = list.map((e) => (e['high'] as num).toDouble());
    final lows = list.map((e) => (e['low'] as num).toDouble());
    final maxP = highs.reduce(math.max);
    final minP = lows.reduce(math.min);
    final span = (maxP - minP).abs() < 0.000001 ? 1.0 : maxP - minP;
    double y(double p) => size.height - ((p - minP) / span * size.height);
    final w = size.width / list.length;
    for (var i = 0; i < list.length; i++) {
      final c = list[i];
      final o = (c['open'] as num).toDouble();
      final h = (c['high'] as num).toDouble();
      final l = (c['low'] as num).toDouble();
      final cl = (c['close'] as num).toDouble();
      final up = cl >= o;
      final paint = Paint()
        ..color = up ? Colors.greenAccent : Colors.redAccent
        ..strokeWidth = 2;
      final x = i * w + w / 2;
      canvas.drawLine(Offset(x, y(h)), Offset(x, y(l)), paint);
      final bodyTop = y(math.max(o, cl));
      final bodyBottom = y(math.min(o, cl));
      final rect = Rect.fromCenter(center: Offset(x, (bodyTop + bodyBottom) / 2), width: (w * .62).clamp(3, 16).toDouble(), height: math.max(3, (bodyBottom - bodyTop).abs()));
      canvas.drawRect(rect, paint);
    }
  }
  @override
  bool shouldRepaint(covariant _CandlePainter oldDelegate) => oldDelegate.candles != candles;
}

class _HistoryList extends StatelessWidget {
  final List<dynamic> history;
  const _HistoryList({required this.history});
  @override
  Widget build(BuildContext context) {
    if (history.isEmpty) return const Text('No trades yet');
    return Column(children: history.take(20).map((e) {
      final m = e as Map<String, dynamic>;
      final result = m['result']?.toString() ?? 'PENDING';
      final color = result == 'WIN' ? Colors.greenAccent : result == 'LOSS' ? Colors.redAccent : Colors.amber;
      return ListTile(
        dense: true,
        title: Text('${m['symbol']}  ${m['direction']}'),
        subtitle: Text('Entry: ${m['entry_price']} | Exit: ${m['exit_price']} | PnL: ${m['pnl']}'),
        trailing: Text(result, style: TextStyle(color: color, fontWeight: FontWeight.bold)),
      );
    }).toList());
  }
}
