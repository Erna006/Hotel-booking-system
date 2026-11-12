import React, {useEffect, useState} from 'react';
import {api} from './api';
import {roomSearchParams, stayQuery} from './roomSearch';
import {count, money, stayLength, today} from './ui';

export function StayPrice({filters, preferredRoom}) {
  const [result, setResult] = useState(null);
  const nights = stayLength(filters.check_in, filters.check_out);
  const capacity = Number(filters.capacity);
  const validPriceRange = Number(filters.min_price) >= 0 && Number(filters.max_price) >= 0 &&
    (!filters.max_price || Number(filters.min_price) <= Number(filters.max_price));
  const ready = nights > 0 && filters.check_in >= today() && Number.isInteger(capacity) &&
    capacity >= 1 && capacity <= 2147483647 && validPriceRange;
  const query = ready ? roomSearchParams(stayQuery(filters, preferredRoom)).toString() : '';

  useEffect(() => {
    if (!query) return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        const prices = await api('/rooms/available/prices?' + query, {signal: controller.signal});
        if (!controller.signal.aborted) setResult({query, prices});
      } catch {
        if (!controller.signal.aborted) setResult({query, error: true});
      }
    }, 200);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  const quote = result?.query === query ? result : null;

  return <div className="stay-price-preview" role="status" aria-atomic="true">
    <div><strong>Стоимость проживания</strong>
      {nights > 0 && <span>{count(nights, 'ночь', 'ночи', 'ночей')}</span>}</div>
    {!query ? <p>{nights > 0 ? 'Проверьте даты и параметры поиска.' : 'Выберите даты заезда и выезда'}</p> :
      !quote ? <p>Проверяем стоимость…</p> :
      quote.error ? <p>Не удалось проверить стоимость. Попробуйте выполнить поиск.</p> :
      quote.prices.length === 0 ? <p>Нет свободных номеров по этим условиям.</p> :
      quote.prices.map(({total_amount, currency}) => <p className="stay-price-amount" key={currency}>
        {!preferredRoom && 'от '}{money(total_amount, currency)}
      </p>)}
  </div>;
}
