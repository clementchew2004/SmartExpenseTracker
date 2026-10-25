import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'

type Props = { name: string; children: ReactNode }
type State = { failed: boolean }

/**
 * Catches a crash while rendering one part of the screen, so the rest keeps working
 * (e.g. a chart bug can't take the quick-add box down with it). React only offers this
 * as a class component - there is no hook version.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { failed: false }

  static getDerivedStateFromError(): State {
    return { failed: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`${this.props.name} crashed:`, error, info.componentStack)
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <div className="card" role="alert">
        <p className="error">The {this.props.name} hit a problem.</p>
        <button type="button" className="secondary" onClick={() => this.setState({ failed: false })}>
          Try again
        </button>
      </div>
    )
  }
}
