import React, {useState, useEffect, useRef} from 'react';
import {createRoot} from 'react-dom/client';
import {api, setToken} from './api';
import './style.css';
const money = (amount, currency) => `${amount} ${currency}`;
const localDate = () => new Intl.DateTimeFormat('en-CA', {timeZone: 'Asia/Qyzylorda', year: 'numeric', month: '2-digit', day: '2-digit'}).format(new Date());

function App() {
  const [user, setUser] = useState(null), [tab, setTab] = useState('rooms');
  const [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [rooms, setRooms] = useState([]), [bookings, setBookings] = useState([]), [users, setUsers] = useState([]);
  const [total, setTotal] = useState(0), [offset, setOffset] = useState(0);
  const [search, setSearch] = useState({check_in: '', check_out: '', capacity: '1', room_type: '', min_price: '', max_price: ''});
  const [searched, setSearched] = useState(null), [register, setRegister] = useState(false);
  const [history, setHistory] = useState({}), [profile, setProfile] = useState(null);
  const attempts = useRef({});
  async function run(work) {
    setBusy(true); setError(''); setNotice('');
    try { await work(); } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  function logout() { setToken(null); setUser(null); setBookings([]); setUsers([]); setHistory({}); attempts.current = {}; setTab('rooms'); }
  useEffect(() => { window.addEventListener('session-expired', logout); return () => window.removeEventListener('session-expired', logout); }, []);
  async function load(next = 0) {
    let result;
    if (tab === 'rooms') {
      result = await api(`/rooms?limit=12&offset=${next}${user?.role === 'admin' ? '&include_inactive=true' : ''}`);
      setRooms(result.items); setSearched(null);
    } else if (tab === 'bookings') { result = await api(`/bookings?limit=12&offset=${next}`); setBookings(result.items); }
    else if (tab === 'users') { result = await api(`/users?limit=12&offset=${next}`); setUsers(result.items); }
    else { setProfile({email: user.email, full_name: user.full_name}); return; }
    setOffset(next); setTotal(result.total);
  }
  useEffect(() => { run(() => load()); }, [tab, user?.id]);
  async function find(next = 0) {
    if (!search.check_in || !search.check_out || search.check_out <= search.check_in) throw new Error('Укажите даты заезда и выезда.');
    const params = new URLSearchParams(Object.entries(search).filter(([, v]) => v !== ''));
    params.set('limit', '12'); params.set('offset', String(next));
    const result = await api(`/rooms/available?${params}`);
    setRooms(result.items); setTotal(result.total); setOffset(next); setSearched({...search});
  }
  async function auth(event) {
    event.preventDefault(); const body = Object.fromEntries(new FormData(event.currentTarget));
    await run(async () => {
      if (register) await api('/auth/register', {method: 'POST', body});
      const data = await api('/auth/login', {method: 'POST', body: {email: body.email, password: body.password}});
      setToken(data.access_token); setUser(await api('/users/me')); setTab('rooms');
    });
  }
  async function pay(booking, outcome) {
    await run(async () => {
      const previous = attempts.current[booking.id];
      const attempt = previous || {key: crypto.randomUUID(), outcome};
      attempts.current[booking.id] = attempt;
      const result = await api(`/bookings/${booking.id}/payments`, {method: 'POST', body: {outcome: attempt.outcome}, key: attempt.key});
      delete attempts.current[booking.id];
      setNotice(result.payment.status === 'failed' ? 'Учебный платёж отклонён. Можно создать новую попытку.' : 'Учебная оплата успешна. Бронь подтверждена.');
      await load(offset);
      setHistory(h => {const copy = {...h}; delete copy[booking.id]; return copy;});
    });
  }
  return <><header><a className="brand" href="#" onClick={() => setTab('rooms')}>Q<span>o</span>naq<span className="brand-dot">.</span></a><nav><button className={tab === 'rooms' ? 'active' : ''} onClick={() => setTab('rooms')}>Номера</button>{user && <><button onClick={() => setTab('bookings')}>{user.role === 'guest' ? 'Мои брони' : 'Все брони'}</button><button onClick={() => setTab('profile')}>Профиль</button>{user.role === 'admin' && <button onClick={() => setTab('users')}>Пользователи</button>}</>}</nav><button onClick={() => user ? logout() : setTab('auth')}>{user ? 'Выйти' : 'Войти →'}</button></header>
  <main><div className="eyebrow">QONAQ HOTEL · КАЗАХСТАН</div><section className="heading"><div><h1>{({rooms: 'Место для вашей паузы.', bookings: 'Ваш следующий заезд.', auth: register ? 'Добро пожаловать.' : 'С возвращением.', users: 'Управление доступом.', profile: 'Ваш профиль.'})[tab]}</h1><p>{tab === 'rooms' ? 'Выберите даты. Найдите свой номер. Почувствуйте себя дома.' : user ? `${user.full_name} · ${user.role}` : 'Войдите, чтобы бронировать номера и управлять поездками.'}</p></div><span className="stamp">STAY<br/>A LITTLE<br/>LONGER ↗</span></section>
  {error && <div role="alert" className="alert">{error}</div>}{notice && <div role="status" className="notice">{notice}</div>}{busy && <p role="status">Загрузка…</p>}
  {tab === 'auth' && <form className="panel auth" onSubmit={auth}>{register && <label>Имя<input name="full_name" required maxLength={200}/></label>}<label>Email<input name="email" type="email" required/></label><label>Пароль<input name="password" type="password" required minLength={register ? 12 : 1} maxLength={128} autoComplete={register ? 'new-password' : 'current-password'}/></label><button disabled={busy} className="primary">{register ? 'Создать аккаунт' : 'Войти'}</button><button type="button" onClick={() => setRegister(!register)}>{register ? 'У меня уже есть аккаунт' : 'Зарегистрироваться'}</button></form>}
  {tab === 'rooms' && <><form className="search panel" onSubmit={e => {e.preventDefault(); run(() => find());}}>{[['check_in','Заезд','date'],['check_out','Выезд','date'],['capacity','Гостей','number'],['room_type','Тип номера','text'],['min_price','Цена от','number'],['max_price','Цена до','number']].map(([key,label,type]) => <label key={key}>{label}<input type={type} min={type === 'date' ? localDate() : key === 'capacity' ? 1 : 0} step={type === 'number' && key !== 'capacity' ? '0.01' : undefined} required={type === 'date'} value={search[key]} onChange={e => {setSearch({...search, [key]: e.target.value}); setSearched(null);}}/></label>)}<button className="primary" disabled={busy}>Найти номер ↗</button></form><div className="section-label"><h2>{searched ? 'Доступно на ваши даты' : 'Наши номера'}</h2><span>{total} вариантов</span></div><div className="grid">{rooms.map((room, i) => <article className="room panel" key={room.id}><div className={'room-art art-' + i % 3}><span>{room.room_type}</span><b>{room.number}</b></div><div className="room-content"><div className="eyebrow">ДО {room.capacity} ГОСТЕЙ{!room.is_active && ' · ОТКЛЮЧЁН'}</div><h3>Номер {room.number}</h3><p className="price">{money(room.price_per_night,room.currency)} <small>/ ночь</small></p>{room.total_amount && <p>За весь период: {money(room.total_amount,room.currency)}</p>}<button disabled={busy || !room.is_active} onClick={() => run(async () => {if (!user) {setTab('auth'); return;} if (!searched) throw new Error('Сначала выполните поиск по датам.'); await api('/bookings', {method:'POST',body:{room_id:room.id,check_in:searched.check_in,check_out:searched.check_out}}); setTab('bookings');})}>Забронировать ↗</button>{user?.role === 'admin' && <RoomEditor room={room} busy={busy} save={body => run(async () => {await api(`/rooms/${room.id}`, {method:'PATCH',body}); await load(offset);})}/>}</div></article>)}</div>{!rooms.length && !busy && <p className="empty">Номера не найдены. Попробуйте другие даты или фильтры.</p>}{user?.role === 'admin' && <section className="panel"><h2>Добавить номер</h2><RoomEditor busy={busy} save={body => run(async () => {await api('/rooms',{method:'POST',body}); await load();})}/></section>}</>}
  {tab === 'bookings' && <div className="stack">{bookings.map(b => <article className="panel booking" key={b.id}><div><span className={'badge ' + b.status}>{b.status}</span><h3>{b.check_in} → {b.check_out}</h3><p>{money(b.total_amount,b.currency)}</p><small>Бронь {b.id}<br/>Номер {b.room_id}</small></div><div className="actions">{b.status !== 'cancelled' && <button disabled={busy} onClick={() => run(async () => {await api(`/bookings/${b.id}/cancel`,{method:'POST'}); await load(offset);})}>Отменить бронь</button>}<button disabled={busy} onClick={() => run(async () => {const h = await api(`/bookings/${b.id}/payments?limit=100`); setHistory({...history,[b.id]:h.items});})}>История платежей</button>{b.status === 'pending' && b.guest_id === user?.id && <div className="simulation"><small>Учебная оплата · деньги не списываются</small><button disabled={busy} onClick={() => pay(b,'succeeded')}>Оплатить успешно</button><button disabled={busy} onClick={() => pay(b,'failed')}>Симулировать отказ</button><small>После сетевой ошибки повторяется та же попытка.</small></div>}</div>{history[b.id] && <div className="history">{history[b.id].length ? history[b.id].map(p => <p key={p.id}>{p.status} · {money(p.amount,p.currency)} · {new Date(p.created_at).toLocaleString()}</p>) : 'Платежей пока нет'}</div>}</article>)}{!bookings.length && !busy && <p className="empty">Бронирований пока нет.</p>}</div>}
  {tab === 'profile' && profile && <form className="panel auth" onSubmit={e => {e.preventDefault(); run(async () => {setUser(await api('/users/me',{method:'PATCH',body:profile})); setNotice('Профиль сохранён.');});}}><label>Имя<input required value={profile.full_name} onChange={e => setProfile({...profile,full_name:e.target.value})}/></label><label>Email<input required type="email" value={profile.email} onChange={e => setProfile({...profile,email:e.target.value})}/></label><button disabled={busy} className="primary">Сохранить</button></form>}
  {tab === 'users' && <div className="stack">{users.map(u => <form key={u.id} className="panel user" onSubmit={e => {e.preventDefault(); const data = new FormData(e.currentTarget); run(async () => {await api(`/users/${u.id}`,{method:'PATCH',body:{role:data.get('role'),is_active:data.has('active')}}); await load(offset); if (u.id === user.id) setUser(await api('/users/me'));});}}><div><h3>{u.full_name}</h3><p>{u.email}</p></div><label>Роль<select name="role" defaultValue={u.role}><option>guest</option><option>receptionist</option><option>admin</option></select></label><label className="check"><input type="checkbox" name="active" defaultChecked={u.is_active}/>Активен</label><button disabled={busy}>Сохранить</button></form>)}</div>}
  {['rooms','bookings','users'].includes(tab) && total > 12 && <div className="pagination"><button disabled={busy || offset === 0} onClick={() => run(() => searched ? find(offset-12) : load(offset-12))}>← Назад</button><span>{offset+1}–{Math.min(offset+12,total)} из {total}</span><button disabled={busy || offset+12 >= total} onClick={() => run(() => searched ? find(offset+12) : load(offset+12))}>Далее →</button></div>}
  </main><footer><span className="brand">Qonaq.</span><p>Тёплый приём начинается здесь.</p><small>Учебная система бронирования · KZT</small></footer></>;
}
function RoomEditor({room,save,busy}) {
  return <details><summary>{room ? 'Редактировать номер' : 'Новый номер'}</summary><form className="editor" onSubmit={e => {e.preventDefault(); const data = Object.fromEntries(new FormData(e.currentTarget)); data.capacity = Number(data.capacity); if(room) data.is_active = data.is_active === 'on'; save(data);}}>{[['number','Номер','text'],['room_type','Тип','text'],['capacity','Вместимость','number'],['price_per_night','Цена за ночь','number'],['currency','Валюта','text']].map(([key,label,type]) => <label key={key}>{label}<input required name={key} type={type} defaultValue={room?.[key] ?? (key === 'currency' ? 'KZT' : '')} min={key === 'capacity' ? 1 : '0.01'} step={key === 'price_per_night' ? '0.01' : undefined} pattern={key === 'currency' ? '[A-Z]{3}' : undefined}/></label>)}{room && <label className="check"><input type="checkbox" name="is_active" defaultChecked={room.is_active}/>Активен</label>}<button disabled={busy}>Сохранить номер</button></form></details>;
}
createRoot(document.getElementById('root')).render(<App/>);
