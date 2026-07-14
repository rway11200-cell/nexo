# Budget Webhook

Webhook that receives expense notifications (CMR, bank, etc.) via Telegram and registers them in Notion.

## Pipeline
1. Tasker on Android captures CMR purchases
2. Sends to Telegram group "Presupuesto CorJar"
3. Fosforito bot processes → registers in Notion "Movimientos" DB
4. Deducts from monthly budget
5. Responds remaining balance
