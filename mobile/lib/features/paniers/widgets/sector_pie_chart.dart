import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../../../models/security.dart';

// Mêmes couleurs que web/src/views/Paniers.jsx:PIE_COLORS.
const _pieColors = [
  Color(0xFFFFB020),
  Color(0xFF3DDC84),
  Color(0xFF5AA9FF),
  Color(0xFFFF5C5C),
  Color(0xFFC58AFF),
  Color(0xFF4FD6C5),
  Color(0xFFE0975A),
  Color(0xFF8B95A1),
  Color(0xFFE85D9A),
  Color(0xFF7FD6FF),
];

/// Répartition sectorielle de l'univers suivi, calculée côté client depuis
/// la liste des titres — miroir de Paniers.jsx's `sectorAgg`.
class SectorPieChart extends StatelessWidget {
  const SectorPieChart({super.key, required this.securities});

  final List<Security> securities;

  @override
  Widget build(BuildContext context) {
    if (securities.isEmpty) {
      return const Text('Aucun titre en base.');
    }
    final counts = <String, int>{};
    for (final s in securities) {
      counts[s.sector] = (counts[s.sector] ?? 0) + 1;
    }
    final entries = counts.entries.toList();

    return Column(
      children: [
        SizedBox(
          height: 220,
          child: PieChart(
            PieChartData(
              sectionsSpace: 1,
              centerSpaceRadius: 55,
              sections: [
                for (var i = 0; i < entries.length; i++)
                  PieChartSectionData(
                    value: entries[i].value.toDouble(),
                    color: _pieColors[i % _pieColors.length],
                    title: '${entries[i].value}',
                    radius: 35,
                    titleStyle: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Colors.white),
                  ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 12,
          runSpacing: 4,
          children: [
            for (var i = 0; i < entries.length; i++)
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(width: 8, height: 8, color: _pieColors[i % _pieColors.length]),
                  const SizedBox(width: 4),
                  Text('${entries[i].key} · ${entries[i].value}', style: Theme.of(context).textTheme.bodySmall),
                ],
              ),
          ],
        ),
      ],
    );
  }
}
