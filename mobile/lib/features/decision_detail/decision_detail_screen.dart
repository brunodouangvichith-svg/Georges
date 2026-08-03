import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../core/theme/app_theme.dart';
import '../../data/decisions_repository.dart';
import '../../data/fundamentals_repository.dart';
import '../../data/patterns_repository.dart';
import '../../data/prices_repository.dart';
import '../../models/decision.dart';
import '../../models/price_bar.dart';
import '../../models/security.dart';
import '../../shared/widgets/response_dialog.dart';
import '../univers/widgets/candlestick_chart.dart';

/// Agrandit la courbe dans un popup au tap — même patron "tap pour le détail"
/// que les tuiles de l'écran Univers (énergie, actualités), plutôt qu'un
/// simple graphique statique inline.
void _showChartPopup(
  BuildContext context, {
  required List<PriceBar> candles,
  required Map<String, dynamic>? patternContext,
  required int indexOffset,
  required double? takeProfit,
  required double? stopLoss,
  required String symbol,
}) {
  showDialog<void>(
    context: context,
    builder: (dialogContext) => Dialog(
      insetPadding: const EdgeInsets.all(16),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(symbol, style: Theme.of(dialogContext).textTheme.titleMedium, textAlign: TextAlign.center),
            const SizedBox(height: 12),
            CandlestickChart(
              candles: candles,
              context: patternContext,
              indexOffset: indexOffset,
              takeProfit: takeProfit,
              stopLoss: stopLoss,
              width: MediaQuery.of(dialogContext).size.width - 64,
              height: 320,
            ),
            const SizedBox(height: 12),
            TextButton(onPressed: () => Navigator.of(dialogContext).pop(), child: const Text('Fermer')),
          ],
        ),
      ),
    ),
  );
}

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
    final fundamentalsAsync = ref.watch(securityFundamentalsProvider(security.symbol));
    final dividendsAsync = ref.watch(securityDividendsProvider(security.symbol));

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
                child: InkWell(
                  borderRadius: BorderRadius.circular(8),
                  onTap: () => _showChartPopup(
                    context,
                    candles: pricesPage.items,
                    patternContext: pattern?.context,
                    indexOffset: indexOffset,
                    takeProfit: decision?.takeProfit,
                    stopLoss: decision?.stopLoss,
                    symbol: security.symbol,
                  ),
                  child: CandlestickChart(
                    candles: pricesPage.items,
                    context: pattern?.context,
                    indexOffset: indexOffset,
                    takeProfit: decision?.takeProfit,
                    stopLoss: decision?.stopLoss,
                    width: 320,
                  ),
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
            FilledButton(
              style: FilledButton.styleFrom(
                backgroundColor: AppColors.accentLight,
                foregroundColor: AppColors.bg,
              ),
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
          Text('Fondamentaux', style: Theme.of(context).textTheme.labelLarge),
          const SizedBox(height: 8),
          fundamentalsAsync.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (e, st) => const Text('—'),
            data: (fundamentals) {
              if (fundamentals == null) {
                return const Text("Aucun instantané disponible pour l'instant (import quotidien pas encore passé).");
              }
              final rows = [
                ['Secteur', fundamentals.sector ?? '—'],
                ['Industrie', fundamentals.industry ?? '—'],
                [
                  'Capitalisation',
                  fundamentals.marketCap != null
                      ? '${(fundamentals.marketCap! / 1e9).toStringAsFixed(2)} Md ${fundamentals.currency ?? ""}'
                      : '—',
                ],
                ['PER (trailing)', fundamentals.trailingPe != null ? fundamentals.trailingPe!.toStringAsFixed(1) : '—'],
                [
                  'Rendement dividende',
                  fundamentals.dividendYield != null ? '${fundamentals.dividendYield!.toStringAsFixed(2)}%' : '—',
                ],
              ];
              return Column(
                children: [
                  for (final row in rows)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 4),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(row[0], style: TextStyle(color: Theme.of(context).colorScheme.outline)),
                          Text(row[1], style: monoTextStyle()),
                        ],
                      ),
                    ),
                  dividendsAsync.maybeWhen(
                    data: (page) => page.items.isEmpty
                        ? const SizedBox.shrink()
                        : Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const SizedBox(height: 8),
                              Text('Derniers dividendes', style: Theme.of(context).textTheme.bodySmall),
                              for (final d in page.items)
                                Padding(
                                  padding: const EdgeInsets.symmetric(vertical: 2),
                                  child: Row(
                                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                    children: [
                                      Text(DateFormat('dd/MM/yyyy').format(d.exDate), style: Theme.of(context).textTheme.bodySmall),
                                      Text('${d.amount.toStringAsFixed(2)} ${fundamentals.currency ?? ""}', style: monoTextStyle(fontSize: 12)),
                                    ],
                                  ),
                                ),
                            ],
                          ),
                    orElse: () => const SizedBox.shrink(),
                  ),
                ],
              );
            },
          ),
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
