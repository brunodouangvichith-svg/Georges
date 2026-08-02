import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/app_theme.dart';
import '../../data/decisions_repository.dart';
import '../../data/patterns_repository.dart';
import '../../data/prices_repository.dart';
import '../../models/decision.dart';
import '../../models/security.dart';
import '../../shared/widgets/response_dialog.dart';
import '../univers/widgets/candlestick_chart.dart';

/// Détail d'un titre + de sa décision la plus récente — écran poussé depuis
/// UniversScreen (équivalent du panneau de détail de web/src/views/Univers.jsx,
/// adapté en écran plein dédié plutôt qu'un 3e panneau, faute de largeur
/// d'écran mobile pour un layout à 3 colonnes).
class DecisionDetailScreen extends ConsumerWidget {
  const DecisionDetailScreen({super.key, required this.security, required this.decision});

  final Security security;
  final Decision? decision;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final patternsAsync = ref.watch(securityPatternsProvider(security.symbol));
    final pricesAsync = ref.watch(securityPricesProvider(security.symbol));

    return Scaffold(
      appBar: AppBar(title: Text(security.name)),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('${security.symbol} · ${security.sector}', style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 12),
          pricesAsync.when(
            loading: () => const SizedBox(height: 150, child: Center(child: CircularProgressIndicator())),
            error: (e, st) => const SizedBox(height: 150),
            data: (pricesPage) {
              final pattern = patternsAsync.value?.items.firstOrNull;
              final indexOffset = pricesPage.total - pricesPage.items.length;
              return Center(
                child: CandlestickChart(
                  candles: pricesPage.items,
                  context: pattern?.context,
                  indexOffset: indexOffset,
                  takeProfit: decision?.takeProfit,
                  stopLoss: decision?.stopLoss,
                  width: 320,
                ),
              );
            },
          ),
          const SizedBox(height: 8),
          patternsAsync.when(
            loading: () => const SizedBox.shrink(),
            error: (e, st) => const SizedBox.shrink(),
            data: (patternsPage) {
              final pattern = patternsPage.items.firstOrNull;
              return Text(
                pattern != null
                    ? 'Figure détectée par George : ${pattern.patternType}'
                    : 'Aucune figure active détectée pour ce titre.',
                style: Theme.of(context).textTheme.bodySmall,
              );
            },
          ),
          const SizedBox(height: 20),
          Text('Raisonnement de George', style: Theme.of(context).textTheme.labelLarge),
          const SizedBox(height: 8),
          Text(
            decision?.rationale ??
                (decision != null
                    ? "Aucune note courte pour cette décision — demandez une analyse à George."
                    : 'Aucune décision enregistrée pour ce titre.'),
          ),
          if (decision != null) ...[
            const SizedBox(height: 12),
            OutlinedButton(
              onPressed: () => showResponseDialog(
                context,
                title: 'George explique — ${security.symbol}',
                loadingText: 'George réfléchit…',
                action: () async {
                  final result = await ref.read(decisionsRepositoryProvider).explain(decision!.id);
                  return result.explanation;
                },
              ),
              child: const Text('Demander une analyse à George'),
            ),
          ],
          const SizedBox(height: 20),
          if (decision != null) ...[
            Text('Niveaux proposés', style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: _LevelCard(
                    label: 'Take-profit',
                    value: decision!.takeProfit,
                    color: AppColors.positive,
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: _LevelCard(
                    label: 'Stop-loss',
                    value: decision!.stopLoss,
                    color: AppColors.negative,
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _LevelCard extends StatelessWidget {
  const _LevelCard({required this.label, required this.value, required this.color});

  final String label;
  final double? value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(border: Border.all(color: Theme.of(context).dividerColor), borderRadius: BorderRadius.circular(8)),
      child: Column(
        children: [
          Text(label, style: Theme.of(context).textTheme.labelSmall),
          const SizedBox(height: 4),
          Text(
            value != null ? '${value!.toStringAsFixed(2)} €' : '—',
            style: monoTextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 15),
          ),
        ],
      ),
    );
  }
}
