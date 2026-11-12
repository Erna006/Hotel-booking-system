export function stayQuery(filters, preferredRoom) {
  return {...filters, room_type: preferredRoom ? '' : filters.room_type.trim(), room_id: preferredRoom?.id ?? ''};
}

export function roomSearchParams(query) {
  return new URLSearchParams(Object.entries(query).filter(([, value]) => value !== ''));
}
