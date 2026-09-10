package com.dynafare.api.controller;

import com.dynafare.api.dto.BookingRequest;
import com.dynafare.api.dto.BookingResponse;
import com.dynafare.api.dto.QuoteRequest;
import com.dynafare.api.dto.QuoteResponse;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping("/api/v1")
public class BookingController {

    @PostMapping("/quotes")
    public ResponseEntity<QuoteResponse> getQuote(@RequestBody QuoteRequest request) {
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
