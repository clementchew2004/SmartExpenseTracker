import { useId } from 'react'

import type { Frequency } from '../api/client'
import { FREQUENCIES, FREQUENCY_LABEL } from '../api/options'
import { dayLabel } from '../dates'

/** null = don't repeat. end_date '' = until you stop it. */
export type RepeatChoice = { frequency: Frequency; end_date: string } | null

type Props = {
  repeat: RepeatChoice
  /** The card's own date: the repeat starts here, so there's no second start box. */
  startDate: string
  onChange: (repeat: RepeatChoice) => void
}

/** Your "Repeat" checkbox; ticking it shows how often and an optional end date. */
export function RepeatOptions({ repeat, startDate, onChange }: Props) {
  const id = useId()

  return (
    <div className="repeat-options">
      <label className="checkbox">
        <input
          type="checkbox"
          checked={repeat !== null}
          onChange={(e) => onChange(e.target.checked ? { frequency: 'monthly', end_date: '' } : null)}
        />
        Repeat
      </label>

      {repeat && (
        <div className="repeat-section">
          <fieldset className="frequency">
            <legend className="visually-hidden">How often</legend>
            {FREQUENCIES.map((f) => (
              <label key={f}>
                <input
                  type="radio"
                  name={`${id}-frequency`}
                  checked={repeat.frequency === f}
                  onChange={() => onChange({ ...repeat, frequency: f })}
                />
                {FREQUENCY_LABEL[f]}
              </label>
            ))}
          </fieldset>
          <p className="muted">Starts {dayLabel(startDate)} (the date above)</p>
          <label>
            Ends <span className="hint">(optional - leave empty to repeat until you stop it)</span>
            <input
              type="date"
              min={startDate}
              value={repeat.end_date}
              onChange={(e) => onChange({ ...repeat, end_date: e.target.value })}
            />
          </label>
        </div>
      )}
    </div>
  )
}
