export function calculateNextDue(event: any): Date {
  const current = new Date(event.subscription.current_end)
  const interval = event.subscription.interval || 'month'
  switch (interval) {
    case 'month': return addMonths(current, 1)
    case 'year': return addYears(current, 1)
    default: return addMonths(current, 1)
  }
}

function addMonths(date: Date, n: number): Date {
  const d = new Date(date)
  d.setMonth(d.getMonth() + n)
  return d
}

function addYears(date: Date, n: number): Date {
  const d = new Date(date)
  d.setFullYear(d.getFullYear() + n)
  return d
}
