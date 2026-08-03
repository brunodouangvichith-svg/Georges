import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/share_repository.dart';

/// Dialogue de réponse partagé — miroir de web/src/components/ResponsePopup.jsx
/// (états loading/done/error, `loadingText` paramétrable par appel). Réutilisé
/// pour toute action qui appelle le backend et affiche un texte en retour :
/// explication de décision, chat, rafraîchissement des prix, collecte macro.
///
/// `symbol` (optionnel, ad hoc — pas une phase du roadmap) : demandé
/// directement par l'utilisateur pour joindre le graphique 10 ans du titre
/// au partage par email quand cette popup est associée à un titre (ex.
/// explication de décision) — omis pour les popups sans titre associé
/// (rafraîchissement des prix, collecte macro...), qui partagent alors le
/// texte seul.
Future<void> showResponseDialog(
  BuildContext context, {
  required String title,
  required String loadingText,
  required Future<String> Function() action,
  String? symbol,
}) {
  return showDialog(
    context: context,
    builder: (context) => _ResponseDialog(title: title, loadingText: loadingText, action: action, symbol: symbol),
  );
}

class _ResponseDialog extends ConsumerStatefulWidget {
  const _ResponseDialog({required this.title, required this.loadingText, required this.action, this.symbol});

  final String title;
  final String loadingText;
  final Future<String> Function() action;
  final String? symbol;

  @override
  ConsumerState<_ResponseDialog> createState() => _ResponseDialogState();
}

class _ResponseDialogState extends ConsumerState<_ResponseDialog> {
  String? _text;
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    widget.action().then((text) {
      if (!mounted) return;
      setState(() {
        _text = text;
        _loading = false;
      });
    }).catchError((Object e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    });
  }

  void _copyText() {
    Clipboard.setData(ClipboardData(text: _text!));
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Texte copié.')));
  }

  Future<void> _shareByEmail() async {
    final toEmail = await showDialog<String>(
      context: context,
      builder: (dialogContext) => _ShareEmailDialog(),
    );
    if (toEmail == null || toEmail.isEmpty) return;
    if (!mounted) return;

    final text = _text!;
    final title = widget.title;
    final symbol = widget.symbol;
    showResponseDialog(
      context,
      title: '📤 Partage par email',
      loadingText: 'Envoi en cours…',
      action: () async {
        final result = await ref.read(shareRepositoryProvider).shareByEmail(
              toEmail: toEmail,
              subject: title,
              text: text,
              symbol: symbol,
            );
        return result.chartAttached
            ? 'Email envoyé à $toEmail, avec le graphique en pièce jointe.'
            : 'Email envoyé à $toEmail.';
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final canShare = !_loading && _error == null && _text != null;

    return AlertDialog(
      title: Text(widget.title),
      content: ConstrainedBox(
        constraints: const BoxConstraints(maxHeight: 400),
        child: SingleChildScrollView(
          child: _loading
              ? Row(
                  children: [
                    const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2)),
                    const SizedBox(width: 12),
                    Expanded(child: Text(widget.loadingText)),
                  ],
                )
              : Text(
                  _error ?? _text ?? '',
                  style: _error != null ? TextStyle(color: Theme.of(context).colorScheme.error) : null,
                ),
        ),
      ),
      actions: [
        if (canShare) ...[
          IconButton(
            tooltip: 'Copier le texte',
            icon: const Text('📋', style: TextStyle(fontSize: 20)),
            onPressed: _copyText,
          ),
          IconButton(
            tooltip: 'Partager par email',
            icon: const Text('📤', style: TextStyle(fontSize: 20)),
            onPressed: _shareByEmail,
          ),
        ],
        TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Fermer')),
      ],
    );
  }
}

class _ShareEmailDialog extends StatefulWidget {
  @override
  State<_ShareEmailDialog> createState() => _ShareEmailDialogState();
}

class _ShareEmailDialogState extends State<_ShareEmailDialog> {
  final _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('📤 Partager par email'),
      content: TextField(
        controller: _controller,
        autofocus: true,
        keyboardType: TextInputType.emailAddress,
        decoration: const InputDecoration(labelText: 'Email', hintText: 'destinataire@exemple.com'),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('❌ Annuler')),
        FilledButton(
          onPressed: () => Navigator.of(context).pop(_controller.text.trim()),
          child: const Text('✅ Envoyer'),
        ),
      ],
    );
  }
}
