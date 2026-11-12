import React, {useId, useRef, useState} from 'react';
import {roomDetails} from './roomDetails';
import {Icon} from './ui';

const types = Object.entries(roomDetails).map(([value, [label]]) => ({value, label}));

function RoomTypePicker({value, onChange}) {
  const [open, setOpen] = useState(false);
  const [custom, setCustom] = useState(false);
  const trigger = useRef(null);
  const menu = useRef(null);
  const customInput = useRef(null);
  const id = useId();
  const known = types.find(type => type.value === value);
  const isCustom = custom || Boolean(value && !known);
  const options = [{value: '', label: 'Все категории'}, ...types];
  const selected = isCustom ? options.length : options.findIndex(type => type.value === value);

  function close(restoreFocus = false) {
    setOpen(false);
    if (restoreFocus) trigger.current?.focus();
  }

  function toggle() {
    if (open) {
      close();
    } else {
      setOpen(true);
      requestAnimationFrame(() => menu.current?.querySelectorAll('button')[selected]?.focus());
    }
  }

  function choose(type) {
    setCustom(false);
    onChange(type.value);
    close(true);
  }

  function chooseCustom() {
    setCustom(true);
    if (!isCustom) onChange('');
    close();
    requestAnimationFrame(() => customInput.current?.focus());
  }

  function onKeyDown(event) {
    if (event.key === 'Escape' && open) {
      event.preventDefault();
      event.stopPropagation();
      close(true);
      return;
    }
    const buttons = Array.from(menu.current?.querySelectorAll('button') || []);
    const index = buttons.indexOf(event.target);
    if (index < 0) return;
    const next = {
      ArrowDown: (index + 1) % buttons.length,
      ArrowUp: (index - 1 + buttons.length) % buttons.length,
      Home: 0,
      End: buttons.length - 1,
    }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    buttons[next].focus();
  }

  return <div className="type-picker" onKeyDown={onKeyDown} onBlur={event => {
    if (!event.currentTarget.contains(event.relatedTarget)) close();
  }}>
    <span id={id + '-label'} className="field-label">Категория</span>
    <button type="button" className="type-trigger" ref={trigger} aria-expanded={open}
      aria-labelledby={id + '-label ' + id + '-value'} aria-controls={id + '-options'} onClick={toggle}>
      <span><Icon name="bed" size={17}/><span id={id + '-value'}>{isCustom ? 'Другая категория' : known?.label || 'Все категории'}</span></span>
      <Icon name="down" size={16}/>
    </button>
    <div id={id + '-options'} className="fold" data-open={open} inert={!open}>
      <div className="fold-content">
        <div className="type-options" ref={menu} role="group" aria-labelledby={id + '-label'}>
          {options.map((type, index) => <button key={type.value} type="button" aria-pressed={selected === index} onClick={() => choose(type)}>
            {type.label}{selected === index && <Icon name="check" size={16}/>}
          </button>)}
          <button type="button" aria-pressed={isCustom} onClick={chooseCustom}>
            Другая категория{isCustom && <Icon name="check" size={16}/>}
          </button>
        </div>
      </div>
    </div>
    {isCustom && <label className="filter-custom">Название категории
      <input ref={customInput} value={value} maxLength={50} placeholder="Введите название"
        onChange={event => onChange(event.target.value)}/>
    </label>}
  </div>;
}

function PriceField({label, value, onChange}) {
  return <label>{label}
    <span className="price-field">
      <input type="number" inputMode="decimal" min="0" step="0.01" placeholder="—" value={value}
        onChange={event => onChange(event.target.value)}/>
      <span aria-hidden="true">₸</span>
    </span>
  </label>;
}

export function RoomFilters({filters, setFilters, preferredRoom}) {
  const [open, setOpen] = useState(false);
  const [resetCount, setResetCount] = useState(0);
  const toggle = useRef(null);
  const id = useId();
  const update = (key, value) => setFilters(current => ({...current, [key]: value}));
  const active = Number(Boolean(!preferredRoom && filters.room_type)) + Number(Boolean(filters.min_price || filters.max_price));

  return <div className="stay-filters">
    <button type="button" className="filter-toggle" ref={toggle} aria-expanded={open} aria-controls={id} onClick={() => setOpen(value => !value)}>
      <span><Icon name="sliders" size={17}/> Фильтры номера{active > 0 && <span className="filter-count">{active}</span>}</span>
      <Icon name="down" size={16}/>
    </button>
    <div id={id} className="fold" data-open={open} inert={!open}>
      <div className="fold-content">
        <div className="filter-content">
          {!preferredRoom && <RoomTypePicker key={resetCount} value={filters.room_type} onChange={value => update('room_type', value)}/>}
          <fieldset className="price-filter">
            <legend>Цена за ночь</legend>
            <div className="price-filter-fields">
              <PriceField label="От" value={filters.min_price} onChange={value => update('min_price', value)}/>
              <PriceField label="До" value={filters.max_price} onChange={value => update('max_price', value)}/>
            </div>
          </fieldset>
          {active > 0 && <button type="button" className="filter-reset text-button" onClick={() => {
            setFilters(current => ({...current, room_type: '', min_price: '', max_price: ''}));
            setResetCount(count => count + 1);
            toggle.current?.focus();
          }}>Сбросить фильтры</button>}
        </div>
      </div>
    </div>
  </div>;
}
