import { db } from '@/lib/db'
import { calculateNextDue } from '@/lib/subscription'

export async function POST(req: Request) {
  const event = await validateWebhook(req)

  if (event.type === 'subscription.charged') {
    await db.subscription.update({
      where: { id: event.subscription_id },
      data: { next_due_on: calculateNextDue(event) }
    })
    return Response.json({ ok: true })
  }

  if (event.type === 'payment.failed') {
    // Don't cancel — mark as pending so retry logic handles it
    await db.subscription.update({
      where: { id: event.subscription_id },
      data: { status: 'pending' }
    })
    return Response.json({ ok: true })
  }

  return Response.json({ ok: true })
}

async function validateWebhook(req: Request) {
  const body = await req.json()
  // In production, verify Razorpay signature here
  return body
}
