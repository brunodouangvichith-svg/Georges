import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:webview_flutter/webview_flutter.dart';

import '../../../data/news_repository.dart';
import '../../../models/news_item.dart';

/// Remplace "Sous-agents — activité récente" dans le tableau de bord de
/// l'écran Univers — mêmes dimensions/style qu'un tuile boxée (voir
/// `MacroTile`). Affiche le titre le plus récent en aperçu ; un tap ouvre un
/// popup flottant (`AlertDialog`, centré par défaut) listant les autres
/// actualités récupérées via yfinance (`api/routers/news.py`, indice CAC 40).
class BreakingNewsTile extends ConsumerWidget {
  const BreakingNewsTile({super.key});

  /// Ouvre l'article dans un popup avec une WebView intégrée, plutôt que de
  /// quitter l'application vers un navigateur externe — demandé directement
  /// par l'utilisateur. `item.url` peut être absent (yfinance ne le fournit
  /// pas toujours) : dans ce cas l'article reste listé mais non cliquable,
  /// jamais un lien cassé.
  void _openArticle(BuildContext context, NewsItem item) {
    if (item.url == null) return;
    showDialog<void>(
      context: context,
      builder: (dialogContext) => Dialog(
        insetPadding: const EdgeInsets.all(16),
        child: SizedBox(
          width: double.maxFinite,
          height: MediaQuery.of(dialogContext).size.height * 0.8,
          child: Column(
            children: [
              AppBar(
                title: Text(item.sourceName, overflow: TextOverflow.ellipsis),
                leading: IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () => Navigator.of(dialogContext).pop(),
                ),
              ),
              Expanded(
                child: WebViewWidget(
                  controller: WebViewController()
                    ..setJavaScriptMode(JavaScriptMode.unrestricted)
                    ..loadRequest(Uri.parse(item.url!)),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showAllNews(BuildContext context, List<NewsItem> items) {
    showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Breaking News'),
        content: SizedBox(
          width: double.maxFinite,
          child: ListView.separated(
            shrinkWrap: true,
            itemCount: items.length,
            separatorBuilder: (_, _) => const Divider(),
            itemBuilder: (context, index) {
              final item = items[index];
              return InkWell(
                onTap: item.url != null ? () => _openArticle(context, item) : null,
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        item.title,
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                              decoration: item.url != null ? TextDecoration.underline : null,
                            ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        item.publishedAt != null
                            ? '${item.sourceName} · ${DateFormat('dd/MM HH:mm').format(item.publishedAt!.toLocal())}'
                            : item.sourceName,
                        style: Theme.of(context).textTheme.labelSmall,
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(), child: const Text('Fermer')),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final newsAsync = ref.watch(newsProvider);

    return InkWell(
      borderRadius: BorderRadius.circular(10),
      onTap: newsAsync.value == null || newsAsync.value!.isEmpty
          ? null
          : () => _showAllNews(context, newsAsync.value!),
      child: Container(
        width: 220,
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(border: Border.all(color: Theme.of(context).dividerColor), borderRadius: BorderRadius.circular(10)),
        child: newsAsync.when(
          loading: () => const Center(child: CircularProgressIndicator(strokeWidth: 2)),
          error: (e, st) => Text('Actualités indisponibles', style: Theme.of(context).textTheme.bodySmall),
          data: (items) {
            if (items.isEmpty) {
              return Text('Aucune actualité pour le moment.', style: Theme.of(context).textTheme.labelSmall);
            }
            final latest = items.first;
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Breaking News', style: Theme.of(context).textTheme.labelSmall),
                const SizedBox(height: 4),
                Text(
                  latest.title,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                const SizedBox(height: 2),
                Text(latest.sourceName, style: Theme.of(context).textTheme.labelSmall),
              ],
            );
          },
        ),
      ),
    );
  }
}
