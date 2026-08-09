import 'dart:async';
import 'dart:convert';
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
  WebSocketChannel? channel;
  StreamSubscription? sub;
  bool running = false;
  bool connecting = false;
  double balance = 0;
  double pnl = 0;
  double price = 0;
  String mode = 'PAPER';
  List<dynamic> history = [];
  List<dynamic> chart = [];
  String lastMessage = 'Waiting for backend...';

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
      channel = ApiService.connectWs();
      sub = channel!.stream.listen((event) {
        final data = jsonDecode(event as String) as Map<String, dynamic>;
        final bal = data['balance'] as Map<String, dynamic>? ?? {};
        final status = data['status'] as Map<String, dynamic>? ?? {};
        setState(() {
          balance = (bal['balance'] as num?)?.toDouble() ?? balance;
          pnl = (bal['session_pnl'] as num?)?.toDouble() ?? pnl;
          mode = bal['mode']?.toString() ?? mode;
          running = status['running'] == true;
          history = (data['history'] as List?) ?? history;
          chart = (data['chart'] as List?) ?? chart;
          price = (data['price'] as num?)?.toDouble() ?? price;
          lastMessage = 'Live: ${DateTime.now().toIso8601String().substring(11, 19)}';
          connecting = false;
        });
      }, onError: (_) {
        setState(() { connecting = false; lastMessage = 'WebSocket error. Check backend IP.'; });
      }, onDone: () {
        setState(() { connecting = false; lastMessage = 'WebSocket closed.'; });
      });
    } catch (e) {
      setState(() { connecting = false; lastMessage = 'WS failed: $e'; });
    }
  }

  Future<void> _start() async {
    try {
      setState(() => lastMessage = 'Starting bot...');
      await ApiService.startBot(
        symbol: symbolCtrl.text.trim(),
        amount: double.tryParse(amountCtrl.text) ?? 1,
        maxTrades: int.tryParse(maxTradesCtrl.text) ?? 10,
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Quotex Bot App'), actions: [
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
          _ConfigPanel(symbolCtrl: symbolCtrl, amountCtrl: amountCtrl, maxTradesCtrl: maxTradesCtrl),
          const SizedBox(height: 12),
          _Panel(title: 'Live Account', child: Text('Mode: $mode\nBalance: ${balance.toStringAsFixed(2)}\nSession PnL: ${pnl.toStringAsFixed(2)}\nBot: ${running ? 'RUNNING' : 'STOPPED'}\n$lastMessage')),
          const SizedBox(height: 12),
          _Panel(title: 'M1 Candlestick / Price Stream', child: SizedBox(height: 180, child: _MiniChart(points: chart, price: price))),
          const SizedBox(height: 12),
          _Panel(title: 'Trade History', child: _HistoryList(history: history)),
        ]),
      ),
    );
  }
}

class _ConfigPanel extends StatelessWidget {
  final TextEditingController symbolCtrl;
  final TextEditingController amountCtrl;
  final TextEditingController maxTradesCtrl;
  const _ConfigPanel({required this.symbolCtrl, required this.amountCtrl, required this.maxTradesCtrl});

  @override
  Widget build(BuildContext context) {
    return _Panel(title: 'Configuration', child: Column(children: [
      TextField(controller: symbolCtrl, decoration: const InputDecoration(labelText: 'Symbol')),
      TextField(controller: amountCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Investment Amount')),
      TextField(controller: maxTradesCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Max Trades')),
      const SizedBox(height: 6),
      const Text('Timeframe: M1 | Expiration: 60s'),
    ]));
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

class _MiniChart extends StatelessWidget {
  final List<dynamic> points;
  final double price;
  const _MiniChart({required this.points, required this.price});
  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      painter: _ChartPainter(points),
      child: Center(child: Text('Live price: ${price.toStringAsFixed(6)}')),
    );
  }
}

class _ChartPainter extends CustomPainter {
  final List<dynamic> points;
  _ChartPainter(this.points);
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = Colors.cyanAccent..strokeWidth = 2..style = PaintingStyle.stroke;
    if (points.length < 2) return;
    final prices = points.map((e) => ((e as Map)['price'] as num).toDouble()).toList();
    final minP = prices.reduce((a, b) => a < b ? a : b);
    final maxP = prices.reduce((a, b) => a > b ? a : b);
    final span = (maxP - minP).abs() < 0.000001 ? 1.0 : maxP - minP;
    final path = Path();
    for (var i = 0; i < prices.length; i++) {
      final x = i / (prices.length - 1) * size.width;
      final y = size.height - ((prices[i] - minP) / span * size.height);
      if (i == 0) path.moveTo(x, y); else path.lineTo(x, y);
    }
    canvas.drawPath(path, paint);
  }
  @override
  bool shouldRepaint(covariant _ChartPainter oldDelegate) => oldDelegate.points != points;
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
