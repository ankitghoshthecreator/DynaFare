package com.dynafare.api.controller;

import com.dynafare.api.domain.Booking;
import com.dynafare.api.domain.Quote;
import com.dynafare.api.domain.Trip;
import com.dynafare.api.domain.User;
import com.dynafare.api.dto.BookingRequest;
import com.dynafare.api.dto.BookingResponse;
import com.dynafare.api.dto.QuoteRequest;
import com.dynafare.api.dto.QuoteResponse;
import com.dynafare.api.dto.DemandEvent;
import com.dynafare.api.repository.BookingRepository;
import com.dynafare.api.repository.QuoteRepository;
import com.dynafare.api.repository.TripRepository;
import com.dynafare.api.repository.UserRepository;
import com.dynafare.api.service.KafkaProducerService;
import com.dynafare.api.service.PricingService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import jakarta.validation.Valid;
import java.time.OffsetDateTime;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
public class BookingController {

    private final KafkaProducerService kafkaProducerService;
    private final PricingService pricingService;
    private final QuoteRepository quoteRepository;
    private final BookingRepository bookingRepository;
    private final TripRepository tripRepository;
    private final UserRepository userRepository;

    @PostMapping("/quotes")
    public ResponseEntity<QuoteResponse> getQuote(@Valid @RequestBody QuoteRequest request, Authentication authentication) {
        User user = userRepository.findByEmail(authentication.getName())
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "User not found"));

        // Get Live ML pricing or Fallback
        Quote quote = pricingService.generateQuote(request, user);
        
        // Save to Database
        quoteRepository.save(quote);

        // Publish demand event
        String zoneId = "zone-nyc-1"; // Dummy zone for Part 4 & 8
        kafkaProducerService.publishDemandEvent(DemandEvent.builder()
                .zoneId(zoneId)
                .delta(1)
                .build());

        QuoteResponse response = QuoteResponse.builder()
                .quoteId(quote.getId())
                .fare(quote.getPredictedPrice())
                .durationMin(quote.getPredictedEta().intValue())
                .expiresAt(quote.getCreatedAt().plusMinutes(10))
                .build();

        return ResponseEntity.ok(response);
    }

    @PostMapping("/bookings")
    public ResponseEntity<BookingResponse> createBooking(@RequestBody BookingRequest request, Authentication authentication) {
        User user = userRepository.findByEmail(authentication.getName())
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED, "User not found"));

        Quote quote = quoteRepository.findById(request.getQuoteId())
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Quote not found"));

        if (!quote.getRider().getId().equals(user.getId())) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Quote belongs to another user");
        }
        
        if (OffsetDateTime.now().isAfter(quote.getCreatedAt().plusMinutes(10))) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Quote expired");
        }

        Trip trip = Trip.builder()
                .rider(user)
                .pickupLat(quote.getPickupLat())
                .pickupLon(quote.getPickupLon())
                .dropoffLat(quote.getDropoffLat())
                .dropoffLon(quote.getDropoffLon())
                .build();
        tripRepository.save(trip);

        Booking booking = Booking.builder()
                .trip(trip)
                .quote(quote)
                .quotedPrice(quote.getPredictedPrice())
                .surgeMultiplier(quote.getSurgeMultiplier())
                .build();
                
        bookingRepository.save(booking);

        BookingResponse response = BookingResponse.builder()
                .bookingId(booking.getId())
                .quoteId(quote.getId())
                .tripId(trip.getId())
                .status(booking.getStatus())
                .amount(booking.getQuotedPrice())
                .createdAt(booking.getCreatedAt())
                .build();

        return ResponseEntity.ok(response);
    }

    @GetMapping("/bookings/{id}")
    public ResponseEntity<BookingResponse> getBooking(@PathVariable UUID id, Authentication authentication) {
        Booking booking = bookingRepository.findById(id)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Booking not found"));
                
        BookingResponse response = BookingResponse.builder()
                .bookingId(booking.getId())
                .quoteId(booking.getQuote().getId())
                .tripId(booking.getTrip().getId())
                .status(booking.getStatus())
                .amount(booking.getQuotedPrice())
                .createdAt(booking.getCreatedAt())
                .build();

        return ResponseEntity.ok(response);
    }
}
