package com.dynafare.api.domain;

/**
 * Booking payment/confirmation status.
 */
public enum BookingStatus {
    PENDING,        // booking created, awaiting confirmation
    CONFIRMED,      // price locked in, driver assigned
    COMPLETED,      // payment settled
    CANCELLED,      // booking cancelled
    REFUNDED        // payment refunded after cancellation
}
