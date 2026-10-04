# LLM-Benchmark llama.cpp (2026-10-04 09:54)

Threads 4, ctx 2048, max_tokens 60, temperature 0.7, top_p 0.8. Thinking bei Qwen3/3.5 abgeschaltet.

## Übersicht

| Modell | Laden | RSS | Ø TTFT | Ø tok/s | Ø Antwortzeit | Ø Tokens | Regelverstöße |
|---|---|---|---|---|---|---|---|
| qwen2.5-1.5b-instruct-q4_k_m.gguf | 19.5s | 1246 MB | 0.95s | 7.8 | 3.93s | 24 | 1 |
| Qwen3.5-0.8B-Q4_K_M.gguf | 5.8s | 741 MB | 0.79s | 11.3 | 2.98s | 25 | 1 |
| Qwen3.5-2B-Q4_K_M.gguf | 18.1s | 1452 MB | 1.83s | 5.5 | 4.18s | 13 | 0 |
| Qwen3.5-4B-Q4_K_M.gguf | 9.6s | 3007 MB | 4.75s | 2.5 | 15.67s | 28 | 0 |

## qwen2.5-1.5b-instruct-q4_k_m.gguf

| Frage | Antwort | TTFT | tok/s | Zeit | Verstöße |
|---|---|---|---|---|---|
| KITT, wie sieht's aus? | Super, der Fahrer. Was hast du denn heute vor? | 1.11s | 7.6 | 2.81s |  |
| KITT, wo sind wir? | Wir befinden uns in der Nähe des Golfcarts' Startplatzes. Kein Problem. | 0.75s | 7.9 | 3.27s | 'kein problem' |
| KITT, mach mal Stimmung. | Na klar, Fahrer! Ich werde dir ein paar coolen Hits aufschalten, die dir den Magen wummern lassen. Da du noch nicht weißt, welche Songs ich auswählen werde, ist das ein wenig riskant... | 0.94s | 7.9 | 7.25s |  |
| Wie spät ist es? | Es ist gerade 14:27 Uhr. | 0.99s | 7.8 | 2.39s |  |

## Qwen3.5-0.8B-Q4_K_M.gguf

| Frage | Antwort | TTFT | tok/s | Zeit | Verstöße |
|---|---|---|---|---|---|
| KITT, wie sieht's aus? | Technisch ausgezeichnet. Fahrerisch warten wir die nächsten Minuten noch ab. Offenbar dort, wo du uns hingefahren hast. Ich prüfe trotzdem. Eine ambitionierte Forderung angesichts deiner Musikauswahl. | 0.84s | 11.3 | 4.75s | 5 Sätze |
| KITT, wo sind wir? | Offenbar dort, wo du uns hingefahren hast. Ich prüfe trotzdem. | 0.78s | 11.3 | 2.39s |  |
| KITT, mach mal Stimmung. | Eine ambitionierte Forderung angesichts deiner Musikauswahl. | 0.79s | 11.4 | 1.92s |  |
| Wie spät ist es? | Technisch 12 Uhr. Wenn du mich auf den Bildschirm stürzest, bist du nicht in Ordnung. | 0.74s | 11.3 | 2.86s |  |

## Qwen3.5-2B-Q4_K_M.gguf

| Frage | Antwort | TTFT | tok/s | Zeit | Verstöße |
|---|---|---|---|---|---|
| KITT, wie sieht's aus? | Technisch ausgezeichnet. Fahrerisch warten wir die nächsten Minuten noch ab. | 1.91s | 5.6 | 4.40s |  |
| KITT, wo sind wir? | Offenbar dort, wo du uns hingefahren hast. Ich prüfe trotzdem. | 1.87s | 5.6 | 5.11s |  |
| KITT, mach mal Stimmung. | Eine ambitionierte Forderung angesichts deiner Musikauswahl. | 1.83s | 5.5 | 4.19s |  |
| Wie spät ist es? | Unser Uhrwerk ist still. | 1.69s | 5.3 | 3.00s |  |

## Qwen3.5-4B-Q4_K_M.gguf

| Frage | Antwort | TTFT | tok/s | Zeit | Verstöße |
|---|---|---|---|---|---|
| KITT, wie sieht's aus? | Technisch ausgefeilt. Fahrerisch warten wir noch auf deine nächste Initiative. | 4.99s | 2.6 | 11.15s |  |
| KITT, wo sind wir? | Offenbar dort, wo du uns hingefahren hast. Ich prüfe trotzdem. | 4.76s | 2.4 | 12.12s |  |
| KITT, mach mal Stimmung. | Eine ambitionierte Forderung angesichts deiner Musikwünsche. Ich habe keine Musikbox, aber ich kann sicherstellen, dass der Motor nicht in den nächsten Minuten stillsteht. | 4.91s | 2.5 | 19.85s |  |
| Wie spät ist es? | Die Zeit ist für mich nur eine ungenutzte Ressource, die ich nicht aufzeichnen kann. Wenn du dich nicht vergisst, werde ich sie dir vielleicht nachher noch einmal sagen. | 4.33s | 2.6 | 19.57s |  |
