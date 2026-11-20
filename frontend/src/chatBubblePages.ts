/** Pages where the chat bubble shows (your choice): Add, the expense list, Insights. */
export function showsChatBubble(pathname: string): boolean {
  return pathname === '/' || pathname === '/expenses' || pathname === '/insights'
}
