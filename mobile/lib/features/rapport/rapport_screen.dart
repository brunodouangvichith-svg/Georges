import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../core/theme/app_theme.dart';
import '../../data/strategic_reports_repository.dart';
import '../../models/strategic_report.dart';
import '../../shared/widgets/empty_state.dart';
import '../../shared/widgets/response_dialog.dart';
import '../trading/trading_screen.dart' show decisionColor;
import 'markdown_blocks.dart';

/// Onglet « Rapport » — miroir mobile de web/src/views/Rapport.jsx (rapport
/// stratégique hebdomadaire, agents/strategic_report.py). Tous les chiffres
/// viennent de `report.data`, calculé en Python côté serveur ; seul le
/// commentaire est rédigé par le LLM. Le portefeuille virtuel est une
/// simulation : aucun ordre réel n'est passé.
class RapportScreen extends ConsumerStatefulWidget {
  const RapportScreen({super.key});

  @override
  ConsumerState<RapportScreen> createState() => _RapportScreenState();
}

const _risk = {
  'vert': ('VERT', AppColors.positive, 'Détente : spread et OAT sous les seuils de vigilance.'),
  'orange': ('ORANGE', AppColors.warning, 'Vigilance : tensions élevées, sans signal de crise de financement.'),
  'rouge': ('ROUGE', AppColors.negative, 'Alerte : OAT et spread au-delà des seuils de tension.'),
  'indetermine': ('INDÉTERMINÉ', AppColors.textDim, 'Données obligataires insuffisantes pour conclure.'),
};

final _num2 = NumberFormat.decimalPatternDigits(locale: 'fr_FR', decimalDigits: 2);
final _num0 = NumberFormat.decimalPatternDigits(locale: 'fr_FR', decimalDigits: 0);
// Formats numériques : pas besoin d'initializeDateFormatting (aucune donnée
// de locale chargée ailleurs dans l'app pour les noms de mois).
final _dateFr = DateFormat('dd/MM/yyyy');
final _dateTimeFr = DateFormat('dd/MM/yyyy HH:mm');

String _n(double? v, {int digits = 2}) => v == null ? '—' : (digits == 0 ? _num0 : _num2).format(v);
String _eur(double? v) => v == null ? '—' : '${_num2.format(v)} €';
String _signed(double? v, {String unit = ' %', int digits = 2}) =>
    v == null ? '—' : '${v > 0 ? '+' : ''}${_n(v, digits: digits)}$unit';
Color _pnlColor(double? v) => v == null || v == 0 ? AppColors.textDim : (v > 0 ? AppColors.positive : AppColors.negative);
String _date(String? iso) {
  final d = iso == null ? null : DateTime.tryParse(iso);
  return d == null ? '—' : _dateFr.format(d.toLocal());
}

class _RapportScreenState extends ConsumerState<RapportScreen> {
  int? _selectedId;

  void _invalidate() {
    ref.invalidate(strategicReportsListProvider);
    ref.invalidate(strategicReportProvider);
  }

  void _generate() {
    showResponseDialog(
      context,
      title: 'Rapport stratégique',
      loadingText: 'George rassemble ses données, cherche l\'actualité et rédige le rapport (1 à 3 min)…',
      shareable: false,
      action: () async {
        await ref.read(strategicReportsRepositoryProvider).generate();
        if (mounted) setState(() => _selectedId = null);
        _invalidate();
        return 'Rapport de la semaine généré.';
      },
    );
  }

  Future<void> _pickHistory(List<StrategicReportSummary> reports) async {
    final picked = await showModalBottomSheet<int?>(
      context: context,
      builder: (context) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          children: [
            ListTile(title: const Text('Dernier rapport'), onTap: () => Navigator.pop(context, -1)),
            for (final r in reports)
              ListTile(
                title: Text(_dateTimeFr.format(r.createdAt.toLocal())),
                trailing: Text(_risk[r.riskLevel]?.$1 ?? r.riskLevel, style: TextStyle(color: _risk[r.riskLevel]?.$2)),
                onTap: () => Navigator.pop(context, r.id),
              ),
          ],
        ),
      ),
    );
    if (picked == null) return;
    setState(() => _selectedId = picked == -1 ? null : picked);
  }

  @override
  Widget build(BuildContext context) {
    final reportAsync = ref.watch(strategicReportProvider(_selectedId));
    final reports = ref.watch(strategicReportsListProvider).value ?? const [];

    return Scaffold(
      appBar: AppBar(
        title: const Text('Rapport stratégique'),
        actions: [
          if (reports.isNotEmpty)
            IconButton(tooltip: 'Historique', icon: const Icon(Icons.history), onPressed: () => _pickHistory(reports)),
          IconButton(tooltip: 'Générer le rapport de la semaine', icon: const Icon(Icons.auto_awesome), onPressed: _generate),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          _invalidate();
          await ref.read(strategicReportProvider(_selectedId).future);
        },
        child: reportAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, st) => ListView(children: const [
            EmptyState(
              message: "Impossible de contacter l'API — le serveur met parfois 1 à 2 minutes à se "
                  'réveiller, réessaie dans un instant.',
            ),
          ]),
          data: (report) => report == null
              ? ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    const EmptyState(
                      message: "Aucun rapport n'a encore été généré. George rassemble ses données "
                          '(obligations, énergie, décisions sur le CAC 40), cherche l\'actualité de la semaine '
                          'et rédige le rapport.',
                    ),
                    FilledButton.icon(
                      onPressed: _generate,
                      icon: const Icon(Icons.auto_awesome),
                      label: const Text('Générer le rapport de la semaine'),
                    ),
                  ],
                )
              : _ReportView(report: report),
        ),
      ),
    );
  }
}

class _ReportView extends StatelessWidget {
  const _ReportView({required this.report});

  final StrategicReport report;

  @override
  Widget build(BuildContext context) {
    final risk = report.risk;
    final level = _risk[report.riskLevel] ?? _risk['indetermine']!;
    final criteria = (risk['criteria'] as Map?)?.cast<String, dynamic>() ?? const {};
    final index = report.cac40Index;
    final brentMatches = report.energy.where((e) => e['code'] == 'BRENT_CRUDE_USD');
    final brent = brentMatches.isEmpty ? null : brentMatches.first;
    final portfolio = report.portfolio;
    final sourceNumbers = {for (final s in report.sources) (s['n'] as num).toInt()};

    return ListView(
      padding: const EdgeInsets.all(12),
      children: [
        Text(
          'Rapport du ${_dateFr.format(report.createdAt.toLocal())} · France, marchés et CAC 40 · horizon 1 à 3 mois',
          style: const TextStyle(fontSize: 11.5, color: AppColors.textDim),
        ),
        const SizedBox(height: 10),
        Card(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12), side: BorderSide(color: level.$2)),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('RISQUE OBLIGATAIRE FRANÇAIS', style: TextStyle(fontSize: 10.5, letterSpacing: 0.8, color: AppColors.textDim)),
                const SizedBox(height: 4),
                Text(level.$1, style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: level.$2)),
                const SizedBox(height: 4),
                Text(level.$3),
                if (criteria.isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Text(
                    'Seuils de suivi de ce rapport, pas des seuils officiels : rouge si ${criteria['rouge']} ; vert si ${criteria['vert']}.',
                    style: const TextStyle(fontSize: 11.5, color: AppColors.textDim),
                  ),
                ],
              ],
            ),
          ),
        ),
        const SizedBox(height: 4),
        GridView.count(
          crossAxisCount: 2,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          childAspectRatio: 1.55,
          mainAxisSpacing: 4,
          crossAxisSpacing: 4,
          children: [
            _Kpi(
              label: 'CAC 40',
              value: index == null ? '—' : _n(numOf(index['close'])),
              sub: index == null ? 'Clôture indisponible' : '${_signed(numOf(index['week_change_pct']))} sur 5 séances',
            ),
            _Kpi(
              label: 'OAT 10 ans',
              value: numOf(risk['oat_10y_pct']) == null ? '—' : '${_n(numOf(risk['oat_10y_pct']))} %',
              sub: 'Observé le ${_date(risk['oat_observed_at'] as String?)}',
            ),
            _Kpi(
              label: 'Spread OAT-Bund',
              value: _signed(numOf(risk['spread_oat_bund_bps']), unit: ' pb', digits: 0),
              sub: numOf(risk['bund_10y_pct']) == null ? 'Bund indisponible' : 'Bund ${_n(numOf(risk['bund_10y_pct']))} %',
            ),
            _Kpi(
              label: 'Brent',
              value: brent == null ? '—' : '${_n(numOf(brent['price']))} \$',
              sub: brent == null ? 'Indisponible' : 'Au ${_date(brent['as_of'] as String?)}',
            ),
          ],
        ),
        const SizedBox(height: 8),
        _Section(
          title: 'Analyse de George',
          child: MarkdownView(markdown: report.narrativeMarkdown, sourceNumbers: sourceNumbers),
        ),
        if (portfolio != null) _PortfolioSection(portfolio: portfolio, pricesAsOf: report.pricesAsOf),
        _Section(
          title: 'Valeurs du CAC 40 (${report.cac40.length})',
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'Décision = dernière décision ouverte de George sur la valeur. Ce ne sont pas des recommandations personnalisées.',
                style: TextStyle(fontSize: 11.5, color: AppColors.textDim),
              ),
              for (final row in report.cac40) _ValueRow(row: row),
            ],
          ),
        ),
        _Section(
          title: 'Sources web (${report.sources.length})',
          child: report.sources.isEmpty
              ? const Text(
                  'Aucune source web pour ce rapport : le commentaire ne s\'appuie que sur les données de George.',
                  style: TextStyle(color: AppColors.textDim),
                )
              : Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    for (final s in report.sources)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: InkWell(
                          onLongPress: () => Clipboard.setData(ClipboardData(text: s['url'] as String? ?? '')),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('[${s['n']}] ${s['titre'] ?? ''}', style: const TextStyle(color: AppColors.accentLight)),
                              SelectableText(
                                '${s['url'] ?? ''} · ${s['theme'] ?? ''}',
                                style: const TextStyle(fontSize: 11, color: AppColors.textDim),
                              ),
                            ],
                          ),
                        ),
                      ),
                  ],
                ),
        ),
        Text(
          'Les chiffres viennent de la base de George et des sources citées ; le commentaire est rédigé par un '
          'modèle de langue${report.modelUsed == null ? '' : ' (${report.modelUsed})'} à partir de ces seules données. '
          'Ce n\'est pas un conseil en investissement.',
          style: const TextStyle(fontSize: 11, color: AppColors.textDim),
        ),
        const SizedBox(height: 16),
      ],
    );
  }
}

class _Section extends StatelessWidget {
  const _Section({required this.title, required this.child});

  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title.toUpperCase(), style: const TextStyle(fontSize: 10.5, letterSpacing: 0.8, color: AppColors.textDim)),
            const SizedBox(height: 8),
            child,
          ],
        ),
      ),
    );
  }
}

class _Kpi extends StatelessWidget {
  const _Kpi({required this.label, required this.value, this.sub, this.color});

  final String label;
  final String value;
  final String? sub;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(label.toUpperCase(), style: const TextStyle(fontSize: 10, letterSpacing: 0.6, color: AppColors.textDim)),
            const SizedBox(height: 2),
            FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.centerLeft,
              child: Text(value, style: TextStyle(fontSize: 19, fontWeight: FontWeight.bold, color: color ?? AppColors.text)),
            ),
            if (sub != null)
              Text(sub!, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 11, color: AppColors.textDim)),
          ],
        ),
      ),
    );
  }
}

class _PortfolioSection extends StatelessWidget {
  const _PortfolioSection({required this.portfolio, required this.pricesAsOf});

  final Map<String, dynamic> portfolio;
  final String? pricesAsOf;

  @override
  Widget build(BuildContext context) {
    final trades = (portfolio['trades'] as List? ?? const []).map((e) => (e as Map).cast<String, dynamic>()).toList();
    final positions = (portfolio['positions'] as List? ?? const []).map((e) => (e as Map).cast<String, dynamic>()).toList();
    final total = numOf(portfolio['total_value']);
    final cash = numOf(portfolio['cash']);
    final sinceStart = numOf(portfolio['performance_since_start_pct']);
    final sincePrevious = numOf(portfolio['performance_since_previous_pct']);

    return _Section(
      title: 'Portefeuille virtuel — simulation',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'Capital initial ${_eur(numOf(portfolio['initial_capital']))} · frais ${_n((numOf(portfolio['fee_rate']) ?? 0) * 100)} % par ordre · '
            'réserve minimale ${_n((numOf(portfolio['min_cash_ratio']) ?? 0) * 100, digits: 0)} % · clôtures au ${_date(pricesAsOf)}. '
            'Aucun ordre réel n\'est passé.',
            style: const TextStyle(fontSize: 11.5, color: AppColors.textDim),
          ),
          const SizedBox(height: 8),
          GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            childAspectRatio: 1.9,
            mainAxisSpacing: 4,
            crossAxisSpacing: 4,
            children: [
              _Kpi(label: 'Valeur totale', value: _eur(total)),
              _Kpi(
                label: 'Liquidités',
                value: _eur(cash),
                sub: total == null || total == 0 || cash == null ? null : '${_n(cash / total * 100, digits: 0)} % du total',
              ),
              _Kpi(label: 'Depuis le départ', value: _signed(sinceStart), color: _pnlColor(sinceStart)),
              _Kpi(
                label: 'Vs rapport précédent',
                value: _signed(sincePrevious),
                color: _pnlColor(sincePrevious),
                sub: portfolio['previous_total_value'] == null
                    ? 'Premier rapport'
                    : 'vs ${_date(portfolio['previous_valued_at'] as String?)}',
              ),
            ],
          ),
          const SizedBox(height: 10),
          const Text('Ordres simulés de ce rapport', style: TextStyle(fontWeight: FontWeight.w600)),
          if (trades.isEmpty)
            const Text('Aucun ordre : aucun signal nouveau ne justifiait d\'achat ou de vente.', style: TextStyle(color: AppColors.textDim))
          else
            for (final t in trades)
              ListTile(
                dense: true,
                contentPadding: EdgeInsets.zero,
                title: Text('${t['side'] == 'achat' ? 'Achat' : 'Vente'} ${t['quantity']} × ${t['name']}'),
                subtitle: Text('${_eur(numOf(t['price']))} · montant ${_eur(numOf(t['gross']))} · frais ${_eur(numOf(t['fees']))}\n${t['rationale'] ?? ''}'),
                isThreeLine: true,
                leading: Icon(
                  t['side'] == 'achat' ? Icons.add_circle_outline : Icons.remove_circle_outline,
                  color: t['side'] == 'achat' ? AppColors.positive : AppColors.negative,
                ),
              ),
          const SizedBox(height: 6),
          const Text('Positions', style: TextStyle(fontWeight: FontWeight.w600)),
          if (positions.isEmpty)
            const Text('Aucune position : tout est en liquidités.', style: TextStyle(color: AppColors.textDim))
          else
            for (final p in positions)
              ListTile(
                dense: true,
                contentPadding: EdgeInsets.zero,
                title: Text('${p['name']}'),
                subtitle: Text(
                  '${p['quantity']} × ${_eur(numOf(p['price']))}'
                  '${p['price_stale'] == true ? ' · cours périmé (dernière clôture ${_date(p['price_as_of'] as String?)})' : ''}',
                ),
                trailing: Text(
                  '${_eur(numOf(p['value']))}\n${numOf(p['weight_pct']) == null ? '' : '${_n(numOf(p['weight_pct']), digits: 1)} %'}',
                  textAlign: TextAlign.right,
                ),
              ),
        ],
      ),
    );
  }
}

class _ValueRow extends StatelessWidget {
  const _ValueRow({required this.row});

  final Map<String, dynamic> row;

  @override
  Widget build(BuildContext context) {
    final decision = row['decision_type'] as String?;
    final change = numOf(row['week_change_pct']);
    final details = [
      if (row['pattern_type'] != null) row['pattern_type'],
      if (numOf(row['confidence']) != null) '${_n(numOf(row['confidence']), digits: 0)} %',
      if (row['portfolio_action'] != null) row['portfolio_action'],
    ].join(' · ');
    // Décision dans le titre plutôt que dans `trailing` : ListTile limite la
    // zone de droite à 48 px de haut, trop peu pour trois lignes.
    return ListTile(
      dense: true,
      contentPadding: EdgeInsets.zero,
      title: Text.rich(
        TextSpan(
          text: '${row['name']}',
          children: [
            if (decision != null)
              TextSpan(
                text: '  $decision',
                style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: decisionColor(decision)),
              ),
          ],
        ),
      ),
      subtitle: Text('${row['sector'] ?? ''}${details.isEmpty ? '' : '\n$details'}'),
      isThreeLine: details.isNotEmpty,
      trailing: Column(
        mainAxisSize: MainAxisSize.min,
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Text(_eur(numOf(row['close'])), style: const TextStyle(fontSize: 13)),
          Text(_signed(change), style: TextStyle(fontSize: 11.5, color: _pnlColor(change))),
        ],
      ),
    );
  }
}

/// Rendu du commentaire Markdown (titres, puces, gras, renvois [n] colorés
/// quand la source n existe dans la liste du rapport).
class MarkdownView extends StatelessWidget {
  const MarkdownView({super.key, required this.markdown, this.sourceNumbers = const {}});

  final String markdown;
  final Set<int> sourceNumbers;

  TextSpan _inline(String text, TextStyle base) {
    return TextSpan(
      style: base,
      children: [
        for (final seg in parseMarkdownInline(text))
          switch (seg.type) {
            'bold' => TextSpan(text: seg.text, style: const TextStyle(fontWeight: FontWeight.bold)),
            'ref' => TextSpan(
                text: '[${seg.ref}]',
                style: TextStyle(fontSize: 11, color: sourceNumbers.contains(seg.ref) ? AppColors.accentLight : null),
              ),
            _ => TextSpan(text: seg.text),
          },
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    const body = TextStyle(fontSize: 14, height: 1.4, color: AppColors.text);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final block in parseMarkdownBlocks(markdown))
          Padding(
            padding: EdgeInsets.only(top: block.type == 'h2' ? 10 : 4, bottom: 2),
            child: switch (block.type) {
              'h2' => Text.rich(_inline(block.text, body.copyWith(fontSize: 15.5, fontWeight: FontWeight.w600))),
              'h3' => Text.rich(_inline(block.text, body.copyWith(fontWeight: FontWeight.w600))),
              'ul' || 'ol' => Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    for (final (i, item) in block.items.indexed)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 3),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            SizedBox(width: 22, child: Text(block.type == 'ul' ? '•' : '${i + 1}.', style: body)),
                            Expanded(child: Text.rich(_inline(item, body))),
                          ],
                        ),
                      ),
                  ],
                ),
              _ => Text.rich(_inline(block.text, body)),
            },
          ),
      ],
    );
  }
}
