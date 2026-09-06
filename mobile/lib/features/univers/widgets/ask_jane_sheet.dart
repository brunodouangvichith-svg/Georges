import 'package:flutter/material.dart';
import 'package:speech_to_text/speech_to_text.dart';

/// Bottom sheet ouvert par le bouton flottant "Ask Jane" (`univers_screen.dart`)
/// — champ texte + commande vocale pour interroger la base de connaissances
/// méthodologique de Jane (`agents/jane.py:ask`). Ne connaît ni le repository
/// ni le dialogue de réponse : `onAsk` (fourni par l'écran appelant) reçoit
/// la question et décide quoi en faire — ce widget se contente de la saisir
/// puis de se fermer, comme `_askChat`/`showResponseDialog` le fait déjà pour
/// le chat de George.
///
/// Première fonctionnalité de commande vocale sur mobile (le web a déjà
/// `useVoiceCapture`, voir `web/src/hooks/useVoiceCapture.js`) — package
/// `speech_to_text`, permission `RECORD_AUDIO` demandée à `initialize()`,
/// jamais au lancement de l'app (voir `AndroidManifest.xml`).
class AskJaneSheet extends StatefulWidget {
  const AskJaneSheet({super.key, required this.onAsk});

  final void Function(String question) onAsk;

  @override
  State<AskJaneSheet> createState() => _AskJaneSheetState();
}

class _AskJaneSheetState extends State<AskJaneSheet> {
  final _controller = TextEditingController();
  final _speech = SpeechToText();
  bool _listening = false;
  bool _speechAvailable = false;

  @override
  void initState() {
    super.initState();
    // Ne bloque jamais l'ouverture du champ texte : si la reconnaissance
    // vocale n'est pas disponible (permission refusée, service absent sur
    // l'appareil, plateforme non supportée), le bouton micro reste
    // simplement désactivé (`_speechAvailable = false`) plutôt que de faire
    // planter la fiche.
    _speech
        .initialize()
        .then((available) {
          if (mounted) setState(() => _speechAvailable = available);
        })
        .catchError((_) {
          if (mounted) setState(() => _speechAvailable = false);
        });
  }

  @override
  void dispose() {
    _speech.stop();
    _controller.dispose();
    super.dispose();
  }

  Future<void> _toggleListening() async {
    if (_listening) {
      await _speech.stop();
      if (mounted) setState(() => _listening = false);
      return;
    }
    if (!_speechAvailable) return;
    setState(() => _listening = true);
    await _speech.listen(
      listenOptions: SpeechListenOptions(localeId: 'fr_FR'),
      onResult: (result) {
        if (!mounted) return;
        setState(() => _controller.text = result.recognizedWords);
        // Auto-soumission sur le résultat final — même comportement que la
        // commande vocale web (`useVoiceCapture`'s onFinal), pour ne pas
        // demander un appui supplémentaire après avoir déjà parlé.
        if (result.finalResult) {
          setState(() => _listening = false);
          _submit();
        }
      },
    );
  }

  void _submit() {
    final question = _controller.text.trim();
    if (question.isEmpty) return;
    Navigator.of(context).pop();
    widget.onAsk(question);
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
        left: 16,
        right: 16,
        top: 16,
        bottom: MediaQuery.of(context).viewInsets.bottom + 16,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '🧠 Analyse Technique — Ask Jane',
            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
          ),
          const SizedBox(height: 4),
          const Text(
            'Interrogez la base de connaissances méthodologique de Jane — définitions, mesures de performance, théorie du portefeuille…',
            style: TextStyle(fontSize: 12),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _controller,
                  autofocus: true,
                  decoration: InputDecoration(
                    hintText: _listening
                        ? 'Je vous écoute…'
                        : 'Votre question pour Jane',
                    border: const OutlineInputBorder(),
                    isDense: true,
                  ),
                  onSubmitted: (_) => _submit(),
                ),
              ),
              const SizedBox(width: 4),
              IconButton(
                tooltip: _listening ? 'Arrêter l\'écoute' : 'Commande vocale',
                icon: Icon(
                  _listening ? Icons.mic : Icons.mic_none,
                  color: _listening
                      ? Theme.of(context).colorScheme.error
                      : null,
                ),
                onPressed: _speechAvailable ? _toggleListening : null,
              ),
              IconButton(icon: const Icon(Icons.send), onPressed: _submit),
            ],
          ),
        ],
      ),
    );
  }
}
