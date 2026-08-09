class BotSnapshot {
  final String eventType;
  final double balance;
  final double pnl;
  final double price;
  final String mode;
  final bool running;
  final Map<String, dynamic>? currentSignal;
  final Map<String, dynamic>? lastAnalysis;
  final Map<String, dynamic>? trade;
  final List<dynamic> history;

  BotSnapshot({
    required this.eventType,
    required this.balance,
    required this.pnl,
    required this.price,
    required this.mode,
    required this.running,
    required this.currentSignal,
    required this.lastAnalysis,
    required this.trade,
    required this.history,
  });

  factory BotSnapshot.fromJson(Map<String, dynamic> data) {
    final bal = data['balance'] as Map<String, dynamic>? ?? {};
    final st = data['status'] as Map<String, dynamic>? ?? {};
    return BotSnapshot(
      eventType: data['type']?.toString() ?? 'snapshot',
      balance: (bal['balance'] as num?)?.toDouble() ?? 0,
      pnl: (bal['session_pnl'] as num?)?.toDouble() ?? 0,
      price: (data['price'] as num?)?.toDouble() ?? 0,
      mode: bal['mode']?.toString() ?? 'PAPER',
      running: st['running'] == true,
      currentSignal: st['current_signal'] as Map<String, dynamic>?,
      lastAnalysis: st['last_analysis'] as Map<String, dynamic>?,
      trade: data['trade'] as Map<String, dynamic>?,
      history: (data['history'] as List?) ?? [],
    );
  }
}
