import React, {useState} from 'react';
import {dateLabel, Feedback, Icon, image} from './ui';

export function Account({mode, switchMode, onSubmit, pending, error, draft, returnHome}) {
  const [visibleFor, setVisibleFor] = useState(null);
  const [email, setEmail] = useState('');
  const [switched, setSwitched] = useState(false);
  const register = mode === 'register';
  const visible = visibleFor === mode;

  function changeMode(next) {
    if (next === mode) return;
    setSwitched(true);
    setVisibleFor(null);
    switchMode(next);
  }

  return <main id="main" className="container auth-page">
    <div className="auth-card">
      <figure className="auth-photo">
        <img src={image('room-suite')} alt="Гостиничный номер с тёплым освещением" width="900" height="700"/>
        <figcaption><Icon name="mark" size={30}/><span>Qonaq Hotel</span></figcaption>
      </figure>
      <div className="auth-content">
        <a className="back-link" href="#top" onClick={returnHome}><Icon name="left" size={17}/> На главную</a>
        <div className="auth-modes" data-register={register} role="group" aria-label="Действие с аккаунтом">
          <button type="button" disabled={pending} aria-pressed={!register} onClick={() => changeMode('login')}>Вход</button>
          <button type="button" disabled={pending} aria-pressed={register} onClick={() => changeMode('register')}>Регистрация</button>
        </div>
        <div key={mode} className="auth-mode-content" data-switched={switched}>
          <h1>{register ? 'Создайте аккаунт' : 'Вход в аккаунт'}</h1>
          <p>{draft ? 'Продолжите оформление бронирования.' :
            register ? 'Управляйте бронированиями и сохраняйте детали поездок.' : 'Войдите, чтобы посмотреть свои бронирования.'}</p>
          {draft && <div className="auth-stay">
            <Icon name="calendar" size={20}/>
            <div><strong>Номер {draft.room.number}</strong>
              <span>{dateLabel(draft.dates.check_in)} — {dateLabel(draft.dates.check_out)}</span></div>
          </div>}
          <Feedback error={error}/>
          <form className="account-form auth-form" onSubmit={onSubmit} aria-busy={pending}>
            {register && <label htmlFor="account-name">Имя и фамилия
              <span className="auth-input"><Icon name="guests" size={18}/>
                <input id="account-name" name="full_name" autoComplete="name" maxLength={200} required/></span>
            </label>}
            <label htmlFor="account-email">Электронная почта
              <span className="auth-input"><Icon name="mail" size={18}/>
                <input id="account-email" name="email" type="email" autoComplete="username" maxLength={254}
                  placeholder="name@example.com" value={email} onChange={event => setEmail(event.target.value)} required/></span>
            </label>
            <div className="auth-password">
              <label htmlFor="account-password">Пароль</label>
              <div className="auth-input password-field">
                <Icon name="lock" size={18}/>
                <input id="account-password" name="password" type={visible ? 'text' : 'password'}
                  autoComplete={register ? 'new-password' : 'current-password'}
                  aria-describedby={register ? 'password-help' : undefined} minLength={register ? 8 : 1} maxLength={128} required/>
                <button type="button" className="icon-button" aria-label={visible ? 'Скрыть пароль' : 'Показать пароль'}
                  onClick={() => setVisibleFor(visible ? null : mode)}><Icon name={visible ? 'eyeOff' : 'eye'}/></button>
              </div>
              {register && <small id="password-help">Не менее 8 символов</small>}
            </div>
            <button className="primary auth-submit" disabled={pending}>
              {pending ? 'Подождите…' : register ? 'Создать аккаунт' : 'Войти'}<Icon name="arrow" size={18}/>
            </button>
          </form>
        </div>
      </div>
    </div>
  </main>;
}
