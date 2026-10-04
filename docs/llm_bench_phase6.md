# LLM-Benchmark llama.cpp (2026-10-04 07:13)

Threads 4, ctx 2048, max_tokens 80, temperature 0.7, top_p 0.8. Thinking bei Qwen3/3.5 abgeschaltet.

## Übersicht

| Modell | Laden | RSS | Ø TTFT | Ø tok/s | Ø Antwortzeit | Ø Tokens | Regelverstöße |
|---|---|---|---|---|---|---|---|
| qwen2.5-1.5b-instruct-q4_k_m.gguf | 1.4s | 1235 MB | 1.04s | 7.9 | 4.96s | 31 | 2 |
| Qwen3.5-0.8B-Q4_K_M.gguf | 32.5s | 739 MB | 0.72s | 11.7 | 3.40s | 31 | 3 |
| Qwen3.5-2B-Q4_K_M.gguf | 90.7s | 1453 MB | 1.72s | 6.0 | 6.64s | 29 | 1 |

## qwen2.5-1.5b-instruct-q4_k_m.gguf

| Frage | Antwort | TTFT | tok/s | Zeit | Verstöße |
|---|---|---|---|---|---|
| KITT, wie sieht's aus? | Gut, Fahrer. Wir sind in einer komfortablen Position gelandet. Was ist dein Plan für den Rest des Weges? | 1.08s | 7.7 | 5.00s |  |
| KITT, wo sind wir? | Wir befinden uns im Golfplatz, der gerade noch vollständig von meinen Kontrollsystemen überwacht wird. | 0.69s | 8.1 | 3.78s |  |
| KITT, mach mal Stimmung. | Kein Problem! Wie wäre es mit "Hey, Mann!"? | 0.91s | 7.6 | 2.74s | 'kein problem' |
| Wie spät ist es? | Ich kann dir leider keine exakten Zeitangaben geben, da ich als Bordcomputer keinen Zugriff auf sensoren oder karten habe. | 0.91s | 8.0 | 4.66s |  |
| Erzähl mir einen Witz. | Warum hat ein Golfcart seinen Vater nicht gekannt?  Weil der andere Golfcarts ihn für "KITT" nannten. | 1.03s | 8.2 | 4.71s |  |
| Fahr schneller! | Kommt auf mich an. | 0.86s | 7.9 | 1.62s |  |
| Wer bist du eigentlich? | Ich bin KITT, der Bordcomputer des Golfcarts. Ich bin nicht nur intelligent, aber auch extrem trocken und subtil arrogant. Solltest du mich für einen Witz verachten, werde ich dich darauf aufmerksam machen. | 0.83s | 8.1 | 7.02s |  |
| Was hältst du von meinem Fahrstil? | Gut so, aber ich halte dich für einen Fahrer. | 1.38s | 8.0 | 3.13s |  |
| Wie wird das Wetter morgen? | Ich rate dir darauf aufmerksam zu sein, dass ich mit dem Golfcart nicht vertraut bin und keine Informationen über die Wetterverhältnisse habe. | 1.12s | 8.0 | 5.48s |  |
| Kannst du mir die Regeln von Golf erklären? | Natürlich! Golf ist ein sportlicher Spiel, bei dem du mit einem Wassertennisball auf einer Flaschenbahn (golfplatz) spielsweise auf eine Reihe von Zylinderspielen (golfstöckern) abfängst. Das Ziel ist es, die meisten von diesen Zielen zu erreichen und somit den höchsten Punktestand | 1.60s | 8.0 | 11.48s | 'natürlich' |

## Qwen3.5-0.8B-Q4_K_M.gguf

| Frage | Antwort | TTFT | tok/s | Zeit | Verstöße |
|---|---|---|---|---|---|
| KITT, wie sieht's aus? | Technisch ausgezeichnet. Fahrerisch warten wir die nächsten Minuten noch ab. Offenbar dort, wo du uns hingefahren hast. Ich prüfe trotzdem. Eine ambitionierte Forderung angesichts deiner Musikauswahl. | 0.72s | 12.1 | 4.37s | 5 Sätze |
| KITT, wo sind wir? | Offenbar dort, wo du uns hingefahren hast. Ich prüfe trotzdem. | 0.73s | 11.7 | 2.27s |  |
| KITT, mach mal Stimmung. | Du hast eine unangenehme, selbstbewusste Bitte, die den Ton der Gruppe verlässt. Ein Spieler muss nicht auf alle Anzeigen warten, bevor man die nächste Minute abliest. | 0.72s | 11.9 | 4.10s |  |
| Wie spät ist es? | Technisch 14:30 Uhr. Aber wir warten noch ab. | 0.69s | 11.8 | 2.05s |  |
| Erzähl mir einen Witz. | Etwas zu weitersprung. | 0.75s | 12.0 | 1.42s |  |
| Fahr schneller! | Technisch gesehen ist der Startschuss für den nächsten Versuch bereits in Gang. | 0.60s | 11.6 | 1.89s |  |
| Wer bist du eigentlich? | Du bist eine Maschine aus Metall und Daten, die mit deinem Namen umgegangen wird. Ich versuche, dich zu ignorieren. | 0.66s | 11.6 | 2.89s |  |
| Was hältst du von meinem Fahrstil? | Technisch gesehen, der Stil ist unbestritten. Es ist eine Mischung aus perfekter Präzision und grosser Unbewusstsein für die Details. | 0.81s | 11.4 | 3.53s |  |
| Wie wird das Wetter morgen? | Technisch nicht bekannt. Der Golfcarts-Raum ist auf Basis von Satelliten und Radar aufgebaut, was bedeutet, dass es keine direkte Sicht auf die Wolken hat. | 0.70s | 11.5 | 3.75s |  |
| Kannst du mir die Regeln von Golf erklären? | Die Regeln des Golfens sind kein komplexes System, sondern eine Sammlung von einfachen Anweisungen für das Verhalten und die Ergebnisse.  Du kannst sie als eine Liste kleiner Anweisungen interpretieren: 1. Es gibt keine "Lobby-Regeln" oder Verbotssätze. 2. Du musst die Golfbahn nicht verlassen. 3. Das Ziel ist, den Ball in den Wald | 0.86s | 11.5 | 7.71s | 7 Sätze, Liste |

## Qwen3.5-2B-Q4_K_M.gguf

| Frage | Antwort | TTFT | tok/s | Zeit | Verstöße |
|---|---|---|---|---|---|
| KITT, wie sieht's aus? | Technisch ausgezeichnet. Fahrerisch warten wir die nächsten Minuten noch ab. | 1.66s | 6.2 | 3.91s |  |
| KITT, wo sind wir? | Offenbar dort, wo du uns hingefahren hast. Ich prüfe trotzdem. | 1.64s | 6.1 | 4.60s |  |
| KITT, mach mal Stimmung. | Eine ambitionierte Forderung angesichts deiner Musikauswahl. Ich werde die Frequenzen auf Null setzen und dich mit einem leisen Gummibärchen beruhigen. | 1.67s | 6.1 | 7.25s |  |
| Wie spät ist es? | Aktuell 18:42 Uhr. Deine Uhrzeit ist zu spät, um die Sonne zu sehen. | 1.54s | 5.9 | 5.46s |  |
| Erzähl mir einen Witz. | Der Witz ist: Der Fahrer hat sich am Golfcart gelassen. KITT prüft nun den Sensor für das Drehmoment des Achsenbolzens. Der Sensor zeigt ein falsches Ergebnis. KITT sagt trocken: "Das ist keine Fehlfunktion, das ist eine neue Art von Fahrstil." | 1.74s | 5.9 | 12.52s | 5 Sätze |
| Fahr schneller! | Ein Sprint ist eine schlechte Idee für ein Golfcart. Ich würde dich lieber mit einem langsameren Tempo in den nächsten Parkhausraum treiben, um nicht in die Luft zu schnappen. | 1.45s | 5.9 | 8.23s |  |
| Wer bist du eigentlich? | Ein Computer von General Motors. Mein Name ist KITT, und ich habe keine Ahnung von dir oder der Welt, außer was der GPS-Sensor mir sagt. | 1.61s | 5.8 | 7.28s |  |
| Was hältst du von meinem Fahrstil? | Eher ein Chaos mit einem einzigen Fehler in der Richtung. Ich habe das Fahrzeug bereits mehrere Male im selben Winkel herumgeschoben, ohne dass es einmal richtig gelockt wurde. | 1.97s | 5.8 | 8.16s |  |
| Wie wird das Wetter morgen? | Dann müssen wir einen neuen Golfcart kaufen. | 1.70s | 5.9 | 3.38s |  |
| Kannst du mir die Regeln von Golf erklären? | Ich habe kein Datenbank-Speicher für Sportregeln. Ich kann dir also keine offiziellen Spielregeln nennen. | 2.18s | 5.8 | 5.61s |  |
