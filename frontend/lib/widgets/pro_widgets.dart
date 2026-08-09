import 'package:flutter/material.dart';

const bg = Color(0xFF030712);
const cardBg = Color(0xBF0F172A);
const gold = Color(0xFFF59E0B);
const cyan = Color(0xFF06B6D4);
const green = Color(0xFF10B981);
const red = Color(0xFFEF4444);
const muted = Color(0xFF9CA3AF);

BoxDecoration glassBox({Color border = const Color(0x22FFFFFF)}) => BoxDecoration(
  color: cardBg,
  borderRadius: BorderRadius.circular(20),
  border: Border.all(color: border),
  boxShadow: [BoxShadow(color: Colors.black.withOpacity(.28), blurRadius: 24, offset: const Offset(0, 10))],
);

class ProCard extends StatelessWidget {
  final Widget child;
  final EdgeInsets padding;
  final Color border;
  const ProCard({super.key, required this.child, this.padding = const EdgeInsets.all(18), this.border = const Color(0x22FFFFFF)});
  @override
  Widget build(BuildContext context) => Container(
    padding: padding,
    decoration: glassBox(border: border),
    child: child,
  );
}

class SectionTitle extends StatelessWidget {
  final String title;
  final Widget? trailing;
  const SectionTitle(this.title, {super.key, this.trailing});
  @override
  Widget build(BuildContext context) => Row(
    children: [
      Expanded(child: Text(title, style: const TextStyle(color: gold, fontSize: 16, fontWeight: FontWeight.w900))),
      if (trailing != null) trailing!,
    ],
  );
}

class StatusPill extends StatelessWidget {
  final String text;
  final Color color;
  const StatusPill(this.text, {super.key, this.color = green});
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
    decoration: BoxDecoration(color: color.withOpacity(.13), borderRadius: BorderRadius.circular(999), border: Border.all(color: color.withOpacity(.35))),
    child: Text(text, style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w800)),
  );
}

InputDecoration proInput(String label, {IconData? icon}) => InputDecoration(
  labelText: label,
  prefixIcon: icon == null ? null : Icon(icon),
  filled: true,
  fillColor: Colors.white.withOpacity(.03),
  border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: Color(0x22FFFFFF))),
  focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: gold)),
);

String fmtMoney(num v) => v.toStringAsFixed(2);
String fmtTime(dynamic seconds) {
  if (seconds == null) return '--:--:--';
  final s = (seconds as num).toInt();
  return DateTime.fromMillisecondsSinceEpoch(s * 1000).toIso8601String().substring(11, 19);
}
