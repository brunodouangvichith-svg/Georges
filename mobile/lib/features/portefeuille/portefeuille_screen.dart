import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../core/theme/app_theme.dart';
import '../../data/portfolios_repository.dart';
import '../../models/portfolio.dart';
import '../../shared/widgets/empty_state.dart';
import '../../shared/widgets/response_dialog.dart';

Color _decisionColor(String type) {
  if (type == 'Achat' || type == 'Renforcer') return AppColors.positive;
  if (type == 'Surveiller') return AppColors.warning;
  return AppColors.negative;
}

Color _pnlColor(double? value) {
  if (value == null) return AppColors.textDim;
  return value >= 0 ? AppColors.positive : AppColors.negative;
}

String _formatPnlPct(double? value) => value == null ? '—' : '${value >= 0 ? '+' : ''}${value.toStringAsFixed(1)}%';

Color _deltaColor(double? value) {
  if (value == null) return AppColors.textDim;
  return value >= 0 ? AppColors.positive : AppColors.negative;
}

String _formatAmount(double value) => '${value >= 0 ? '+' : ''}${value.toStringAsFixed(2)} €';

/// Portefeuilles nommés créés depuis Paniers — miroir de
/// web/src/views/MonPortefeuille.jsx, sans la variante vocale de "Demander à
/// George" (budget saisi via un champ numérique simple, voir la décision de
/// périmètre V1 : pas de STT natif).
class PortefeuilleScreen extends ConsumerWidget {
  const PortefeuilleScreen({super.key});

  void _askGeorge(BuildContext context, WidgetRef ref, Portfolio portfolio) {
    final controller = TextEditingController();
    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Demander à George'),
        content: TextField(
          controller: controller,
          autofocus: true,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          decoration: const InputDecoration(labelText: 'Budget à répartir (€)', hintText: 'ex. 50000'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(), child: const Text('Annuler')),
          FilledButton(
            onPressed: () {
              final budget = double.tryParse(controller.text.replaceAll(',', '.'));
              if (budget == null || budget <= 0) return;
              Navigator.of(dialogContext).pop();
              showResponseDialog(
                context,
                title: 'Demander à George — ${portfolio.name}',
                loadingText: 'Répartition du budget en cours…',
                action: () async {
                  final result = await ref.read(portfoliosRepositoryProvider).allocate(portfolio.id, budget);
                  ref.invalidate(portfoliosProvider);
                  return result.summary;
                },
              );
            },
            child: const Text('Répartir'),
          ),
        ],
      ),
    );
  }

  Future<void> _confirmDelete(BuildContext context, WidgetRef ref, Portfolio portfolio) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Supprimer le portefeuille ?'),
        content: Text('« ${portfolio.name} » sera définitivement supprimé.'),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(false), child: const Text('Annuler')),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            style: FilledButton.styleFrom(backgroundColor: Colors.red.shade400),
            child: const Text('Supprimer'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    await ref.read(portfoliosRepositoryProvider).delete(portfolio.id);
    ref.invalidate(portfoliosProvider);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final portfoliosAsync = ref.watch(portfoliosProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Mon Portefeuille')),
      body: RefreshIndicator(
        onRefresh: () => ref.refresh(portfoliosProvider.future),
        child: portfoliosAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, st) => ListView(
            children: const [
              EmptyState(
                message:
                    "Impossible de contacter l'API — si le service vient d'être "
                    'inactif, le premier appel peut prendre jusqu\'à ~50s '
                    '(réveil du plan gratuit Render), sinon vérifiez la connexion.',
              ),
            ],
          ),
          data: (portfolios) {
            if (portfolios.isEmpty) {
              return ListView(
                children: const [
                  EmptyState(
                    message: "Aucun portefeuille. Allez sur l'écran Paniers, cochez des décisions "
                        'puis cliquez « Créer un portefeuille ».',
                  ),
                ],
              );
            }
            return ListView.builder(
              padding: const EdgeInsets.all(12),
              itemCount: portfolios.length,
              itemBuilder: (context, index) => _PortfolioSection(
                portfolio: portfolios[index],
                onAskGeorge: () => _askGeorge(context, ref, portfolios[index]),
                onDelete: () => _confirmDelete(context, ref, portfolios[index]),
              ),
            );
          },
        ),
      ),
    );
  }
}

class _PortfolioSection extends ConsumerWidget {
  const _PortfolioSection({required this.portfolio, required this.onAskGeorge, required this.onDelete});

  final Portfolio portfolio;
  final VoidCallback onAskGeorge;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final dateFormat = DateFormat('dd/MM/yyyy');
    final timeFormat = DateFormat('HH:mm');

    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(portfolio.name, style: Theme.of(context).textTheme.titleMedium),
                ),
                IconButton(
                  tooltip: 'Supprimer le portefeuille',
                  icon: Icon(Icons.delete_outline, color: Colors.red.shade400),
                  onPressed: onDelete,
                ),
              ],
            ),
            Align(
              alignment: Alignment.centerLeft,
              child: OutlinedButton.icon(
                onPressed: onAskGeorge,
                icon: const Icon(Icons.mic_none, size: 16),
                label: const Text('Demander à George pour répartir le portefeuille'),
                style: OutlinedButton.styleFrom(
                  backgroundColor: Colors.lightBlue.shade100,
                  foregroundColor: Colors.black87,
                ),
              ),
            ),
            const SizedBox(height: 4),
            Text('Créé le ${dateFormat.format(portfolio.createdAt)}', style: Theme.of(context).textTheme.labelSmall),
            const SizedBox(height: 8),
            if (portfolio.decisions.isEmpty)
              const Text('Ce portefeuille est vide.')
            else ...[
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: DataTable(
                  columns: const [
                    DataColumn(label: Text('Ticker')),
                    DataColumn(label: Text('Entrée')),
                    DataColumn(label: Text('Prix')),
                    DataColumn(label: Text('Delta veille')),
                    DataColumn(label: Text('TP')),
                    DataColumn(label: Text('SL')),
                    DataColumn(label: Text('PnL')),
                    DataColumn(label: Text('Confiance')),
                    DataColumn(label: Text('Qté')),
                    DataColumn(label: Text('Date/Heure')),
                    DataColumn(label: Text('')),
                  ],
                  rows: [
                    for (final pd in portfolio.decisions)
                      DataRow(cells: [
                        DataCell(Text(pd.decision.symbol,
                            style: TextStyle(color: _decisionColor(pd.decision.decisionType), fontWeight: FontWeight.bold))),
                        DataCell(Text('${pd.decision.entryPrice.toStringAsFixed(2)} €')),
                        DataCell(Text(pd.currentPrice != null ? '${pd.currentPrice!.toStringAsFixed(2)} €' : '—')),
                        DataCell(Text(_formatPnlPct(pd.dayChangePct), style: TextStyle(color: _deltaColor(pd.dayChangePct)))),
                        DataCell(Text(pd.decision.takeProfit != null ? '${pd.decision.takeProfit!.toStringAsFixed(2)} €' : '—')),
                        DataCell(Text(pd.decision.stopLoss != null ? '${pd.decision.stopLoss!.toStringAsFixed(2)} €' : '—')),
                        DataCell(Text(_formatPnlPct(pd.pnlPct), style: TextStyle(color: _pnlColor(pd.pnlPct), fontWeight: FontWeight.bold))),
                        DataCell(Text('${pd.decision.confidence.toStringAsFixed(0)}%')),
                        DataCell(Text(pd.quantity?.toString() ?? '—')),
                        DataCell(Text(pd.priceUpdatedAt != null
                            ? '${dateFormat.format(pd.priceUpdatedAt!)} ${timeFormat.format(pd.priceUpdatedAt!)}'
                            : '—')),
                        DataCell(
                          TextButton(
                            onPressed: () async {
                              await ref.read(portfoliosRepositoryProvider).removeDecision(portfolio.id, pd.decision.id);
                              ref.invalidate(portfoliosProvider);
                            },
                            child: const Text('Retirer'),
                          ),
                        ),
                      ]),
                  ],
                ),
              ),
              const Divider(),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'PnL du portefeuille',
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(color: Colors.lightBlueAccent, fontWeight: FontWeight.bold),
                  ),
                  if (portfolio.totalPnlAmount == null)
                    const Expanded(
                      child: Text(
                        'Renseignez des quantités (« Demander à George ») pour calculer le PnL total.',
                        textAlign: TextAlign.end,
                        style: TextStyle(fontSize: 11),
                      ),
                    )
                  else
                    Text(
                      '${_formatAmount(portfolio.totalPnlAmount!)}'
                      '${portfolio.totalInvested != null && portfolio.totalInvested! > 0 ? ' (${_formatPnlPct(portfolio.totalPnlAmount! / portfolio.totalInvested! * 100)})' : ''}',
                      style: TextStyle(color: _pnlColor(portfolio.totalPnlAmount), fontWeight: FontWeight.bold),
                    ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}
