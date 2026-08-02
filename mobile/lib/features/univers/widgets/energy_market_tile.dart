import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../data/energy_prices_repository.dart';
import '../../../models/energy_price.dart';

const _energyLabels = {
  'BRENT_CRUDE_USD': 'Brent',
  'WTI_USD': 'WTI',
  'NATURAL_GAS_USD': 'Gaz naturel',
  'DIESEL_USD': 'Diesel',
  'HEATING_OIL_USD': 'Fioul domestique',
  'GASOLINE_USD': 'Essence',
};
const _energyOrder = ['BRENT_CRUDE_USD', 'WTI_USD', 'NATURAL_GAS_USD', 'DIESEL_USD', 'HEATING_OIL_USD', 'GASOLINE_USD'];

/// Remplace l'ancienne tuile "Repères macro (donnée fictive)" — mêmes
/// dimensions/style, mais branchée sur de vraies données (OilPriceAPI, voir
/// `api/routers/energy.py`/`ingestion/energy_prices.py`) : Brent, WTI, gaz
/// naturel, produits raffinés. Tap ouvre un popup avec le détail (variation
/// 24h, unité), même patron que la tuile macro qu'elle remplace.
class EnergyMarketTile extends ConsumerWidget {
  const EnergyMarketTile({super.key});

  List<EnergyPrice> _sorted(List<EnergyPrice> prices) =>
      [for (final code in _energyOrder) prices.where((p) => p.commodityCode == code).firstOrNull].whereType<EnergyPrice>().toList();

  void _showDetail(BuildContext context, List<EnergyPrice> prices) {
    showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text("Marché d'énergie"),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            for (final p in prices)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(_energyLabels[p.commodityCode] ?? p.commodityCode),
                    Text(
                      '${(p.change24hPct ?? 0) >= 0 ? '▲' : '▼'} ${p.price.toStringAsFixed(2)} ${p.currency}/${p.unit}',
                      style: TextStyle(
                        color: (p.change24hPct ?? 0) >= 0 ? Colors.green.shade400 : Colors.red.shade400,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(), child: const Text('Fermer')),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final pricesAsync = ref.watch(energyPricesProvider);

    return InkWell(
      borderRadius: BorderRadius.circular(10),
      onTap: pricesAsync.value == null || pricesAsync.value!.isEmpty
          ? null
          : () => _showDetail(context, _sorted(pricesAsync.value!)),
      child: Container(
        width: 170,
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(border: Border.all(color: Theme.of(context).dividerColor), borderRadius: BorderRadius.circular(10)),
        child: pricesAsync.when(
          loading: () => const Center(child: CircularProgressIndicator(strokeWidth: 2)),
          error: (e, st) => Text("Marché d'énergie indisponible", style: Theme.of(context).textTheme.bodySmall),
          data: (prices) {
            final sorted = _sorted(prices);
            if (sorted.isEmpty) {
              return Text('Aucune donnée pour le moment.', style: Theme.of(context).textTheme.labelSmall);
            }
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text("Marché d'énergie", style: Theme.of(context).textTheme.labelSmall, maxLines: 2),
                const SizedBox(height: 4),
                for (final p in sorted)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 1),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Expanded(
                          child: Text(
                            _energyLabels[p.commodityCode] ?? p.commodityCode,
                            style: Theme.of(context).textTheme.bodySmall,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        const SizedBox(width: 4),
                        Text(
                          '${(p.change24hPct ?? 0) >= 0 ? '▲' : '▼'} ${p.price.toStringAsFixed(2)}',
                          style: TextStyle(
                            color: (p.change24hPct ?? 0) >= 0 ? Colors.green.shade400 : Colors.red.shade400,
                            fontSize: 11,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            );
          },
        ),
      ),
    );
  }
}
