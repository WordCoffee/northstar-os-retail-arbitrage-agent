import { useState } from 'react'

export default function Recovery() {
  return (
    <div className="fade-in">
      <div style={{ maxWidth: 420, margin: '60px auto' }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <h2>Recovery</h2>
          <p className="text-mid" style={{ fontSize: 13 }}>Reset your credentials or verify your identity.</p>
        </div>
        <div className="card">
          <div className="stack" style={{ gap: 16 }}>
            <div className="field-group">
              <label className="label">Organization ID</label>
              <input className="field" placeholder="Enter your organization identifier" />
            </div>
            <div className="field-group">
              <label className="label">Verification Method</label>
              <select className="field">
                <option>Email verification</option>
                <option>Organization admin recovery</option>
                <option>Hardware key</option>
              </select>
            </div>
            <button className="btn btn-primary btn-block">Send Recovery Link</button>
            <p className="text-low" style={{ fontSize: 12, textAlign: 'center' }}>Recovery links expire after 48 hours.</p>
          </div>
        </div>
      </div>
    </div>
  )
}