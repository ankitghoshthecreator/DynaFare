package com.dynafare.api.controller;

import com.dynafare.api.domain.DriverStatus;
import com.dynafare.api.domain.User;
import com.dynafare.api.repository.DriverRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
public class UserController {

    private final DriverRepository driverRepository;

    @GetMapping("/users/me")
    public ResponseEntity<User> getCurrentUser(@AuthenticationPrincipal User user) {
        // user is injected by Spring Security from the SecurityContext
        return ResponseEntity.ok(user);
    }

    @PatchMapping("/drivers/{id}/status")
    public ResponseEntity<Void> updateDriverStatus(
            @PathVariable UUID id,
            @RequestParam DriverStatus status
    ) {
        var driver = driverRepository.findById(id)
                .orElseThrow(() -> new IllegalArgumentException("Driver not found"));
        driver.setStatus(status);
        driverRepository.save(driver);
        return ResponseEntity.ok().build();
    }
}
