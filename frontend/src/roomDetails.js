export const roomDetails = {
  standard: ['Классический', 'room-standard', 'Уютный номер с тёплой отделкой из дерева для короткого отдыха вдвоём.'],
  deluxe: ['Делюкс', 'room-deluxe', 'Двухместный номер с мягким диваном и отдельным уголком для отдыха.'],
  studio: ['Студия', 'room-studio', 'Светлая студия с большими окнами и местом для работы или чтения.'],
  family: ['Семейный', 'room-family', 'Просторный номер для семьи или компании до четырёх гостей.'],
  suite: ['Люкс', 'room-suite', 'Камерный люкс с приглушённым светом и отделкой из тёмного дерева.'],
  residence: ['Резиденция', 'room-residence', 'Номер для длительной поездки с зоной отдыха и обеденным столом.'],
};

export function detailsFor(room) {
  const key = room.room_type.toLowerCase();
  return Object.hasOwn(roomDetails, key) ? roomDetails[key] : [room.room_type, 'room-standard', ''];
}
