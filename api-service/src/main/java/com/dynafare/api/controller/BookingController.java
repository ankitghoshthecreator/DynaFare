package com.dynafare.api.controller;

import com.dynafare.api.dto.BookingRequest;
import com.dynafare.api.dto.BookingResponse;
import com.dynafare.api.dto.QuoteRequest;
import com.dynafare.api.dto.QuoteResponse;
import com.dynafare.api.dto.DemandEvent;
import com.dynafare.api.service.KafkaProducerService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
public class BookingController {

    private final KafkaProducerService kafkaProducerService;

    @PostMapping("/quotes")
    public ResponseEntity<QuoteResponse> getQuote(@RequestBody QuoteRequest request) {
        // Publish demand event (assuming pickup zone is derived from lat/lon in a real system)
        // For now, we'll use a dummy zone or require zoneId in the request
        String zoneId = "zone-nyc-1"; // Dummy zone for Part 4
        kafkaProducerService.publishDemandEvent(DemandEvent.builder()
                .zoneId(zoneId)
                .delta(1) // 1 user requesting a quote
                .build());

        // TODO: Part 8 Pricing Integration
        return ResponseEntity.status(HttpStatus.NOT_IMPLEMENTED).build();
    }

    @PostMapping("/bookings")
    public ResponseEntity<BookingResponse> createBooking(@RequestBody BookingRequest request) {
        // TODO: Part 8 Pricing Integration
        return ResponseEntity.status(HttpStatus.NOT_IMPLEMENTED).build();
    }

    @GetMapping("/bookings/{id}")
    public ResponseEntity<BookingResponse> getBooking(@PathVariable UUID id) {
        // TODO: Part 8 Pricing Integration
        return ResponseEntity.status(HttpStatus.NOT_IMPLEMENTED).build();
    }
}
