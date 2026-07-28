/// Miroir de `api/schemas.py:ExplanationResponse`.
class Explanation {
  final String explanation;
  final String? secondOpinion;

  Explanation({required this.explanation, this.secondOpinion});

  factory Explanation.fromJson(Map<String, dynamic> json) => Explanation(
        explanation: json['explanation'] as String,
        secondOpinion: json['second_opinion'] as String?,
      );
}
