# Migration Guide: Run ID to Run Name

This document outlines the changes made to migrate from run IDs (UUIDs) to run names (e.g., "run 1", "run 2", etc.).

## Changes Completed

### 1. SDK Core Changes ✅
- **Files Modified:**
  - `sdk/gati/core/event.py`: Changed `generate_run_id()` to `generate_run_name()` with auto-increment support
  - `sdk/gati/core/context.py`: Updated all `run_id` references to `run_name` throughout the context management system
  - `sdk/gati/decorators/track_agent.py`: Updated to use `run_name` instead of `run_id`
  - `sdk/gati/observe.py`: Updated context retrieval to use `get_current_run_name()`

### 2. Database Schema Changes ✅
- **Migration File Created:** `backend/alembic/versions/002_run_id_to_run_name.py`
  - Changes primary key from `run_id` to composite key `(agent_name, run_name)`
  - Migrates existing data to run names based on creation order
  - Updates foreign key relationships
  - Adds unique constraint on `(agent_name, run_name)`

### 3. Backend Models ✅
- **Files Modified:**
  - `backend/app/models/run.py`: Changed primary key to composite `(agent_name, run_name)`
  - `backend/app/models/event.py`: Updated foreign key to reference composite key

### 4. API Schemas ✅
- **Files Modified:**
  - `backend/app/schemas/run.py`: Updated all `run_id` fields to `run_name`
  - `backend/app/schemas/event.py`: Updated all `run_id` fields to `run_name`
  - Added `RunUpdateRequest` schema for updating run names

### 5. Backend API - Events ✅
- **File Modified:** `backend/app/api/events.py`
  - Updated `_ensure_runs_exist()` function to handle auto-increment logic
  - Detects `temp_*` run names and converts them to `run {number}` format
  - Maintains highest run number per agent for auto-increment

### 6. Backend API - Runs (Partially Complete)
- **File Modified:** `backend/app/api/runs.py`
  - ✅ Updated imports to include `RunUpdateRequest`
  - ✅ Updated `get_run_details()` endpoint to use `/runs/{agent_name}/{run_name}`

## Remaining Changes Needed

### Backend API - Runs Endpoints

Update the following endpoints in `backend/app/api/runs.py`:

1. **Timeline Endpoint** (Line 78):
   ```python
   # Change from:
   @router.get("/runs/{run_id}/timeline", ...)

   # To:
   @router.get("/runs/{agent_name}/{run_name}/timeline", ...)

   # Update all run_id references to agent_name + run_name
   ```

2. **Trace Endpoint** (Line 139):
   ```python
   # Change from:
   @router.get("/runs/{run_id}/trace", ...)

   # To:
   @router.get("/runs/{agent_name}/{run_name}/trace", ...)
   ```

3. **Delete Endpoint** (Line 221):
   ```python
   # Change from:
   @router.delete("/runs/{run_id}")

   # To:
   @router.delete("/runs/{agent_name}/{run_name}")

   # Update queries:
   stmt = select(Run).where(
       Run.agent_name == agent_name,
       Run.run_name == run_name
   )

   delete_events_stmt = sql_delete(Event).where(
       Event.agent_name == agent_name,
       Event.run_name == run_name
   )
   ```

4. **Add Update Endpoint** (New):
   ```python
   @router.patch("/runs/{agent_name}/{run_name}")
   async def update_run_name(
       agent_name: str,
       run_name: str,
       update_request: RunUpdateRequest,
       session: AsyncSession = Depends(get_async_session),
   ) -> RunDetailResponse:
       """Update a run's name."""
       try:
           # Check if run exists
           stmt = select(Run).where(
               Run.agent_name == agent_name,
               Run.run_name == run_name
           )
           result = await session.execute(stmt)
           run = result.scalar_one_or_none()

           if not run:
               raise HTTPException(
                   status_code=status.HTTP_404_NOT_FOUND,
                   detail=f"Run '{run_name}' for agent '{agent_name}' not found",
               )

           # Check if new name already exists
           check_stmt = select(Run).where(
               Run.agent_name == agent_name,
               Run.run_name == update_request.new_run_name
           )
           check_result = await session.execute(check_stmt)
           existing_run = check_result.scalar_one_or_none()

           if existing_run:
               raise HTTPException(
                   status_code=status.HTTP_400_BAD_REQUEST,
                   detail=f"Run name '{update_request.new_run_name}' already exists for agent '{agent_name}'",
               )

           # Update run name
           run.run_name = update_request.new_run_name
           await session.commit()
           await session.refresh(run)

           return RunDetailResponse(
               run_name=run.run_name,
               agent_name=run.agent_name,
               environment=run.environment,
               status=run.status,
               total_duration_ms=run.total_duration_ms or 0,
               total_cost=run.total_cost,
               tokens_in=run.tokens_in,
               tokens_out=run.tokens_out,
               metadata=run.run_metadata,
               created_at=run.created_at.isoformat(),
               event_count=len(run.events) if run.events else 0,
           )
       except HTTPException:
           raise
       except Exception as e:
           await session.rollback()
           logger.error(f"Error updating run name: {str(e)}", exc_info=True)
           raise HTTPException(
               status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
               detail="Failed to update run name",
           ) from e
   ```

### Backend API - Agents Endpoints

Update queries in `backend/app/api/agents.py`:

- Change all `select(Run.run_id)` to `select(Run.run_name)`
- Update response building to use `run_name` instead of `run_id`

### Frontend Changes

#### 1. Types (`dashboard/src/types/index.ts`):
```typescript
export interface Run {
  run_name: string;  // Changed from run_id
  agent_name: string;
  environment?: string;
  status?: string;
  total_duration_ms?: number;
  total_cost?: number;
  tokens_in?: number;
  tokens_out?: number;
  created_at: string;
}

// Update all other interfaces that reference run_id
```

#### 2. API Client (`dashboard/src/services/api.ts`):
```typescript
async fetchRun(agentName: string, runName: string): Promise<Run> {
  const response = await fetch(`${this.baseURL}/runs/${agentName}/${runName}`);
  // ...
}

async fetchRunTimeline(agentName: string, runName: string): Promise<RunTimelineResponse> {
  const response = await fetch(`${this.baseURL}/runs/${agentName}/${runName}/timeline`);
  // ...
}

async fetchRunTrace(agentName: string, runName: string): Promise<ExecutionTraceResponse> {
  const response = await fetch(`${this.baseURL}/runs/${agentName}/${runName}/trace`);
  // ...
}

async deleteRun(agentName: string, runName: string): Promise<void> {
  await fetch(`${this.baseURL}/runs/${agentName}/${runName}`, {
    method: 'DELETE',
  });
}

async updateRunName(agentName: string, runName: string, newRunName: string): Promise<Run> {
  const response = await fetch(`${this.baseURL}/runs/${agentName}/${runName}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ new_run_name: newRunName }),
  });
  return response.json();
}
```

#### 3. Components:

**RunDetail.tsx:**
- Change `run.run_id` to `run.run_name` throughout
- Update API calls to use `(run.agent_name, run.run_name)`
- Add inline editing for run name with validation

**AgentRuns.tsx:**
- Change `run.run_id` to `run.run_name`
- Display full run name instead of truncated UUID
- Update delete handler to use `(run.agent_name, run.run_name)`

**AgentDetail.tsx:**
- Update all run references to use `run_name`
- Update filter logic in delete handlers

**ExecutionTree.tsx & FlowGraph.tsx:**
- Remove `run_id` from filtered display fields

**EventDetailPanel.tsx:**
- Display `run_name` instead of `run_id`

## Testing Checklist

After implementing remaining changes:

1. **Backend:**
   - [ ] Run database migration
   - [ ] Test event ingestion with temp names
   - [ ] Verify auto-increment logic works correctly
   - [ ] Test run name update endpoint with duplicate name validation
   - [ ] Test all CRUD operations on runs

2. **Frontend:**
   - [ ] Verify runs display with new names
   - [ ] Test run name editing from UI
   - [ ] Verify validation prevents duplicate names
   - [ ] Test delete operations
   - [ ] Check all timeline and trace views

3. **Integration:**
   - [ ] Run an agent from SDK and verify run name auto-increments
   - [ ] Verify events are correctly associated with run names
   - [ ] Test multiple concurrent agents
   - [ ] Verify parent-child run relationships still work

## Backward Compatibility Notes

- The migration automatically converts existing UUIDs to numbered run names
- Old SDK versions will not work with the new backend
- Frontend and backend must be updated together
