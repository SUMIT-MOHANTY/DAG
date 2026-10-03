// ─── ContextDrawer ────────────────────────────────────────────────────────────
import React, { useState, useEffect } from 'react';
import type { BookingContext } from '@/features/policies/types';

interface ContextDrawerProps {
  isOpen: boolean;
  context: BookingContext;
  onClose: () => void;
  onSave: (ctx: BookingContext) => void;
}

const ContextDrawer: React.FC<ContextDrawerProps> = ({ isOpen, context, onClose, onSave }) => {
  const [form, setForm] = useState<BookingContext>(context);

  useEffect(() => {
    setForm(context);
  }, [context]);

  const handleChange = (field: keyof BookingContext, value: string | number) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleChildAgesChange = (raw: string) => {
    const ages = raw
      .split(',')
      .map((s) => parseInt(s.trim(), 10))
      .filter((n) => !isNaN(n));
    setForm((prev) => ({ ...prev, child_ages: ages }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave(form);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/30 z-40 animate-fade-in"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer */}
      <div
        className="fixed right-0 top-0 h-full w-full max-w-md bg-white shadow-2xl z-50 flex flex-col animate-slide-in"
        role="dialog"
        aria-modal="true"
        aria-label="Modify Booking Context"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-200">
          <div>
            <h2 className="text-base font-bold text-neutral-900">Modify Context</h2>
            <p className="text-xs text-neutral-500 mt-0.5">Update booking context for future queries</p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-neutral-400 hover:text-neutral-700 hover:bg-neutral-100 transition-colors"
            aria-label="Close drawer"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          {/* Booking ID */}
          <div>
            <label className="block text-xs font-semibold text-neutral-600 mb-1.5">
              Booking ID
            </label>
            <input
              type="text"
              value={form.booking_id}
              onChange={(e) => handleChange('booking_id', e.target.value)}
              placeholder="e.g. BK-2847"
              className="w-full px-3 py-2 text-sm border border-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition"
            />
          </div>

          {/* Property */}
          <div>
            <label className="block text-xs font-semibold text-neutral-600 mb-1.5">
              Property
            </label>
            <input
              type="text"
              value={form.property ?? ''}
              onChange={(e) => handleChange('property', e.target.value)}
              placeholder="e.g. Grand Ocean Resort"
              className="w-full px-3 py-2 text-sm border border-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition"
            />
          </div>

          {/* Room Type */}
          <div>
            <label className="block text-xs font-semibold text-neutral-600 mb-1.5">
              Room Type
            </label>
            <select
              value={form.room_type ?? ''}
              onChange={(e) => handleChange('room_type', e.target.value)}
              className="w-full px-3 py-2 text-sm border border-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition bg-white"
            >
              <option value="">Select room type...</option>
              <option value="standard">Standard Room</option>
              <option value="deluxe">Deluxe Room</option>
              <option value="suite">Suite</option>
              <option value="family">Family Room</option>
              <option value="villa">Villa</option>
              <option value="penthouse">Penthouse</option>
            </select>
          </div>

          {/* Guest counts */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-neutral-600 mb-1.5">
                Adults
              </label>
              <input
                type="number"
                min={1}
                max={20}
                value={form.adult_count}
                onChange={(e) => handleChange('adult_count', parseInt(e.target.value, 10) || 1)}
                className="w-full px-3 py-2 text-sm border border-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-neutral-600 mb-1.5">
                Children
              </label>
              <input
                type="number"
                min={0}
                max={20}
                value={form.child_count}
                onChange={(e) => handleChange('child_count', parseInt(e.target.value, 10) || 0)}
                className="w-full px-3 py-2 text-sm border border-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition"
              />
            </div>
          </div>

          {/* Child ages */}
          {form.child_count > 0 && (
            <div>
              <label className="block text-xs font-semibold text-neutral-600 mb-1.5">
                Child Ages <span className="font-normal text-neutral-400">(comma-separated)</span>
              </label>
              <input
                type="text"
                value={(form.child_ages ?? []).join(', ')}
                onChange={(e) => handleChildAgesChange(e.target.value)}
                placeholder="e.g. 5, 8, 12"
                className="w-full px-3 py-2 text-sm border border-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition"
              />
            </div>
          )}

          {/* Travel dates */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-neutral-600 mb-1.5">
                Check-in
              </label>
              <input
                type="date"
                value={form.check_in ?? ''}
                onChange={(e) => handleChange('check_in', e.target.value)}
                className="w-full px-3 py-2 text-sm border border-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-neutral-600 mb-1.5">
                Check-out
              </label>
              <input
                type="date"
                value={form.check_out ?? ''}
                onChange={(e) => handleChange('check_out', e.target.value)}
                className="w-full px-3 py-2 text-sm border border-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition"
              />
            </div>
          </div>
        </form>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-neutral-200 flex gap-3">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 px-4 py-2 text-sm font-medium text-neutral-700 bg-neutral-100 hover:bg-neutral-200 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            form="context-form"
            onClick={handleSubmit}
            className="flex-1 px-4 py-2 text-sm font-semibold text-white bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors shadow-sm"
          >
            Apply Context
          </button>
        </div>
      </div>
    </>
  );
};

export default ContextDrawer;
