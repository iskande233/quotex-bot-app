import 'package:flutter/material.dart';

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

class BotHomePage extends StatelessWidget {
  const BotHomePage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Quotex Bot App')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(children: [
              Expanded(child: ElevatedButton.icon(onPressed: () {}, icon: const Icon(Icons.play_arrow), label: const Text('START'))),
              const SizedBox(width: 12),
              Expanded(child: ElevatedButton.icon(onPressed: () {}, icon: const Icon(Icons.stop), label: const Text('STOP'))),
            ]),
            const SizedBox(height: 16),
            const _Panel(title: 'Balance', child: Text('Paper mode: 1000.00 | Session PnL: 0.00')),
            const SizedBox(height: 16),
            const _Panel(title: 'M1 Candlestick Chart', child: SizedBox(height: 180, child: Center(child: Text('Chart placeholder')))),
            const SizedBox(height: 16),
            const _Panel(title: 'Trade History', child: Text('No trades yet')),
          ],
        ),
      ),
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
